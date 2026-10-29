"""yt-dlp engine: option building, metadata probing and the download worker.

yt-dlp is used as an embedded library — AnyDownloader never spawns external
processes or servers. FFmpeg ships with the app via ``imageio-ffmpeg``.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

from anydownloader.core import paths
from anydownloader.core.models import DownloadJob, JobState, JobOptions, QualityProfile, profile_by_id

log = logging.getLogger(__name__)

try:  # yt-dlp >= 2023.01
    from yt_dlp.utils import DownloadCancelled
except Exception:  # pragma: no cover
    class DownloadCancelled(Exception):  # type: ignore[no-redef]
        pass


# --------------------------------------------------------------------- ffmpeg
_ffmpeg_exe_cache: Optional[str] = None


def ffmpeg_exe() -> Optional[str]:
    """Full path to a usable ffmpeg binary, or None."""
    global _ffmpeg_exe_cache
    if _ffmpeg_exe_cache is not None:
        return _ffmpeg_exe_cache or None
    exe = ""
    try:
        import imageio_ffmpeg  # bundled with the app / wheel

        found = imageio_ffmpeg.get_ffmpeg_exe()
        if found and Path(found).is_file():
            exe = str(found)
    except Exception:  # pragma: no cover - fall back to system install
        pass
    if not exe:
        found = shutil.which("ffmpeg")
        if found:
            exe = str(found)
    _ffmpeg_exe_cache = exe
    return exe or None


def ffmpeg_dir() -> Optional[str]:
    """Directory containing a binary literally named ffmpeg(.exe), or None."""
    exe = ffmpeg_exe()
    if exe and Path(exe).name.lower().replace(".exe", "") == "ffmpeg":
        return str(Path(exe).parent)
    return None


def ytdlp_version() -> str:
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:  # pragma: no cover
        return "unknown"


# ------------------------------------------------------------- format strings
def build_format_selector(profile: QualityProfile, container: str) -> str:
    if profile.kind == "audio":
        return "bestaudio/best"
    h = profile.height
    if h is None:  # best available
        return "bestvideo+bestaudio/best"
    if container == "mp4":
        return (
            f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={h}]+bestaudio/"
            f"best[height<={h}]/best"
        )
    return (
        f"bestvideo[height<={h}]+bestaudio/"
        f"best[height<={h}]/best"
    )


def output_template(opts: JobOptions, kind: str) -> str:
    """Compose the final output template (dir + optional site folder + filename)."""
    out_dir = opts.download_dir or str(paths.default_download_dir())
    if opts.organize == "type":
        out_dir = os.path.join(out_dir, "Audio" if kind == "audio" else "Video")
    prefix = "%(webpage_url_domain)s/" if opts.organize == "site" else ""
    template = opts.template.strip() or "%(title)s.%(ext)s"
    if "%(ext)s" not in template:
        template += ".%(ext)s"
    return os.path.join(out_dir, prefix + template)


# ----------------------------------------------------------------- options
def _base_options(proxy: str = "", cookies_browser: str = "", cookies_file: str = "") -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "logger": _YtdlpLogger(),
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "nocheckcertificate": False,
    }
    if proxy:
        opts["proxy"] = proxy
    if cookies_file and Path(cookies_file).is_file():
        opts["cookiefile"] = cookies_file
    elif cookies_browser:
        opts["cookiesfrombrowser"] = (cookies_browser,)
    ffmpeg_exe_path = ffmpeg_exe()
    if ffmpeg_exe_path:
        # Full binary path: imageio-ffmpeg ships a versioned filename that a
        # directory-style ffmpeg_location would not resolve.
        opts["ffmpeg_location"] = ffmpeg_exe_path
    return opts


def build_download_options(job: DownloadJob) -> dict[str, Any]:
    """Full yt-dlp option dict for a job (used by DownloadWorker)."""
    opts = job.options
    profile = job.profile
    opts_ydl = _base_options(opts.proxy, opts.cookies_browser, opts.cookies_file)

    opts_ydl["outtmpl"] = {"default": output_template(opts, profile.kind)}
    opts_ydl["format"] = build_format_selector(profile, opts.container)
    if opts.restrict_names:
        opts_ydl["restrictfilenames"] = True
    if opts.concurrent_fragments > 1:
        opts_ydl["concurrent_fragment_downloads"] = opts.concurrent_fragments
    if opts.speed_limit_bytes > 0:
        opts_ydl["ratelimit"] = opts.speed_limit_bytes

    # Playlists
    if opts.playlist_mode == "single":
        opts_ydl["noplaylist"] = True
    elif opts.playlist_mode == "range" and opts.playlist_range.strip():
        opts_ydl["playlist_items"] = opts.playlist_range.strip()

    # Post-processors
    pps: list[dict[str, Any]] = []
    if opts.sponsors_remove and profile.kind == "video":
        pps.append({"key": "SponsorBlock", "when": "pre_process"})
        pps.append({"key": "ModifyChapters", "remove_sponsor_segments": ["sponsor"]})

    if profile.kind == "audio":
        pps.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": profile.audio_codec,
            "preferredquality": "0" if profile.audio_codec == "mp3" else "5",
            "nopostoverwrites": True,
        })
    elif opts.container != "original":
        opts_ydl["merge_output_format"] = opts.container

    if profile.kind == "video" and opts.subtitle_enabled:
        langs = [p for p in opts.subtitle_langs.replace(",", " ").split() if p]
        opts_ydl["writesubtitles"] = True
        if opts.subtitle_auto:
            opts_ydl["writeautomaticsub"] = True
        if langs:
            opts_ydl["subtitleslangs"] = langs
        opts_ydl["subtitlesformat"] = "srt/vtt/best"
        if opts.subtitle_embed:
            pps.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})

    if opts.embed_metadata:
        opts_ydl["add_metadata"] = True
        opts_ydl["add_chapters"] = True
        pps.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})
    if opts.embed_thumbnail:
        opts_ydl["writethumbnail"] = True
        pps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    if pps:
        opts_ydl["postprocessors"] = pps
    if opts.use_archive:
        opts_ydl["download_archive"] = str(paths.archive_path())
    return opts_ydl


def probe_options(noplaylist: bool = True) -> dict[str, Any]:
    opts = _base_options()
    opts.update({
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": noplaylist,
    })
    return opts


class _YtdlpLogger:
    """Route yt-dlp debug output into our log (kept out of the console)."""

    def debug(self, msg: str) -> None:
        if msg.startswith("[error]") or "ERROR:" in msg:
            log.debug("%s", msg.strip())

    def info(self, msg: str) -> None:  # pragma: no cover - verbose only
        log.debug("%s", msg.strip())

    def warning(self, msg: str) -> None:  # pragma: no cover
        log.debug("%s", msg.strip())

    def error(self, msg: str) -> None:
        log.error("%s", msg.strip())


# -------------------------------------------------------------------- probing
def probe(url: str, *, proxy: str = "", cookies_browser: str = "",
          cookies_file: str = "") -> dict[str, Any]:
    """Fetch metadata for preview. Returns a simplified dict. Raises on error."""
    import yt_dlp

    opts = _base_options(proxy, cookies_browser, cookies_file)
    opts.update({
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": True,
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        raw = ydl.extract_info(url, download=False)
    if not raw:
        raise RuntimeError("Could not extract video information from this link.")
    return _summarize_info(ydl.sanitize_info(raw))


def _summarize_info(info: dict[str, Any]) -> dict[str, Any]:
    is_playlist = info.get("_type") == "playlist"
    entries = info.get("entries") or []
    summary: dict[str, Any] = {
        "id": info.get("id"),
        "title": info.get("title") or info.get("webpage_url") or "Untitled",
        "uploader": info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url") or info.get("original_url"),
        "extractor": info.get("extractor_key") or info.get("extractor") or "",
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "upload_date": info.get("upload_date"),
        "is_playlist": is_playlist,
        "entry_count": len(entries) if entries else None,
        "entries": [
            {"title": e.get("title") or e.get("url"), "url": e.get("url") or e.get("webpage_url"),
             "duration": e.get("duration")}
            for e in entries[:200]
        ] if is_playlist else [],
        "formats": [],
    }
    for f in reversed(info.get("formats") or []):
        if f.get("vcodec") in (None, "none"):
            continue
        height = f.get("height")
        if not height:
            continue
        label = f"{height}p"
        if f.get("fps"):
            label += f" {int(f['fps'])}fps"
        row = {
            "label": label,
            "ext": f.get("ext") or "?",
            "height": height,
            "size": f.get("filesize") or f.get("filesize_approx"),
            "hdr": f.get("dynamic_range") in ("HDR10", "Dolby Vision", "HDR"),
        }
        if not any(r["label"] == row["label"] for r in summary["formats"]):
            summary["formats"].append(row)
    summary["formats"] = summary["formats"][:8]
    return summary


# -------------------------------------------------------------------- worker
class DownloadWorker(QThread):
    """Runs one yt-dlp download on its own thread; reports via signals."""

    updated = Signal(object)          # DownloadJob (fields mutated)
    state_changed = Signal(object)    # DownloadJob with new JobState
    finished_job = Signal(object, object)   # job, info dict
    failed = Signal(object, str)      # job, error message
    cancelled = Signal(object)        # job

    def __init__(self, job: DownloadJob, parent=None) -> None:
        super().__init__(parent)
        self.job = job
        self._opts = build_download_options(job)

    # ------------------------------------------------------------- hooks
    def _progress_hook(self, d: dict[str, Any]) -> None:
        if self.job.cancel_event.is_set():
            raise DownloadCancelled("Cancelled by user")
        job = self.job
        status = d.get("status")
        if status == "downloading":
            info = d.get("info_dict") or {}
            job.state = JobState.DOWNLOADING
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes") or 0
            if total:
                job.total_bytes = int(total)
                job.downloaded_bytes = int(downloaded)
                job.progress_percent = min(100.0, downloaded / total * 100.0)
            job.speed = d.get("speed")
            job.eta = d.get("eta")
            if info.get("playlist_index") is not None:
                job.playlist_index = info.get("playlist_index")
                job.playlist_count = info.get("n_entries")
                job.entry_title = info.get("title") or job.entry_title
            if not job.title and info.get("title"):
                self._absorb_info(info)
            self.updated.emit(job)
        elif status == "finished":
            job.downloaded_bytes = job.total_bytes or job.downloaded_bytes
            job.progress_percent = 100.0 if not job.playlist_count else job.progress_percent
            job.speed = None
            job.eta = None
            self.updated.emit(job)

    def _pp_hook(self, d: dict[str, Any]) -> None:
        if self.job.cancel_event.is_set():
            raise DownloadCancelled("Cancelled by user")
        job = self.job
        if d.get("status") == "started":
            job.state = JobState.POSTPROCESSING
            job.speed = None
            job.eta = None
            self.state_changed.emit(job)
        elif d.get("status") == "finished":
            job.state = JobState.DOWNLOADING
            self.updated.emit(job)

    def _absorb_info(self, info: dict[str, Any]) -> None:
        job = self.job
        job.title = info.get("title") or job.title
        job.uploader = info.get("uploader") or info.get("channel") or job.uploader
        job.duration = info.get("duration") or job.duration
        job.thumbnail_url = info.get("thumbnail") or job.thumbnail_url
        job.webpage_url = info.get("webpage_url") or job.url

    # ------------------------------------------------------------- run
    def run(self) -> None:  # noqa: C901 - linear worker flow
        import yt_dlp

        job = self.job
        opts = dict(self._opts)
        opts["progress_hooks"] = [self._progress_hook]
        opts["postprocessor_hooks"] = [self._pp_hook]
        ydl = yt_dlp.YoutubeDL(opts)
        try:
            job.state = JobState.DOWNLOADING
            self.state_changed.emit(job)
            info = ydl.extract_info(job.url, download=True)
            info = ydl.sanitize_info(info) if info else {}
            if info:
                self._absorb_info(info)
                outputs = self._collect_filepaths(info)
                if outputs:
                    job.output_path = outputs[0]
                    job.output_paths = outputs  # type: ignore[attr-defined]
            job.state = JobState.COMPLETED
            job.progress_percent = 100.0
            job.completed_at = time.time()
            job.speed = None
            job.eta = None
            self.finished_job.emit(job, info or {})
        except DownloadCancelled:
            job.state = JobState.CANCELLED
            job.completed_at = time.time()
            job.speed = None
            job.eta = None
            self.cancelled.emit(job)
        except Exception as exc:
            message = _clean_error(exc)
            log.warning("download failed (%s): %s", job.url, message)
            job.state = JobState.FAILED
            job.error = message
            job.completed_at = time.time()
            job.speed = None
            job.eta = None
            self.failed.emit(job, message)
        finally:
            try:
                ydl.close()
            except Exception:  # pragma: no cover
                pass

    @staticmethod
    def _collect_filepaths(info: dict[str, Any]) -> list[str]:
        found: list[str] = []
        sources = [info] + list(info.get("entries") or [])
        for item in sources:
            for rd in item.get("requested_downloads") or []:
                path = rd.get("filepath")
                if path and path not in found:
                    found.append(path)
        return found


def _clean_error(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    message = lines[-1] if lines else text
    if len(message) > 400:
        message = message[:397] + "…"
    lowered = message.lower()
    hints = {
        "private video": "This video is private.",
        "sign in to confirm your age": "Age-restricted video — enable cookies from your browser in Settings → Network.",
        "http error 429": "Rate limited by the site — wait a few minutes and retry.",
        "unsupported url": "This website is not supported yet.",
        "is not a valid url": "That does not look like a valid link.",
        "no video formats": "No downloadable media found at this link.",
        "unable to download webpage": "Could not reach the website — check your connection or proxy.",
        "failed to open": "Could not read cookies from the browser — try exporting a cookies.txt file instead.",
    }
    for needle, hint in hints.items():
        if isinstance(needle, str) and needle and needle in lowered:
            return hint
    return message


def start_worker(job: DownloadJob, parent=None) -> DownloadWorker:
    worker = DownloadWorker(job, parent)
    job.worker_ref = worker
    worker.start()
    return worker


# Kept for API clarity elsewhere
def cancel_job(job: DownloadJob) -> None:
    job.cancel_event.set()


def fetch_title(url: str) -> dict[str, Any]:
    """Lightweight metadata fetch for queue rows (best effort)."""
    import yt_dlp

    opts = probe_options(noplaylist=True)
    with yt_dlp.YoutubeDL(opts) as ydl:
        raw = ydl.extract_info(url, download=False)
    if not raw:
        raise RuntimeError("no info")
    return {
        "title": raw.get("title"),
        "uploader": raw.get("uploader") or raw.get("channel"),
        "duration": raw.get("duration"),
        "thumbnail": raw.get("thumbnail"),
        "webpage_url": raw.get("webpage_url"),
        "n_entries": raw.get("n_entries") if raw.get("_type") == "playlist" else None,
    }
