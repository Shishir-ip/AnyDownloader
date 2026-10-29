"""Data model: download jobs, quality profiles and per-job option snapshots."""
from __future__ import annotations

import enum
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


class JobState(enum.Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    POSTPROCESSING = "postprocessing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (JobState.COMPLETED, JobState.CANCELLED, JobState.FAILED)

    @property
    def is_active(self) -> bool:
        return self in (JobState.DOWNLOADING, JobState.POSTPROCESSING)


STATE_LABEL = {
    JobState.QUEUED: "Queued",
    JobState.DOWNLOADING: "Downloading",
    JobState.POSTPROCESSING: "Processing",
    JobState.COMPLETED: "Completed",
    JobState.CANCELLED: "Cancelled",
    JobState.FAILED: "Failed",
}


@dataclass(frozen=True)
class QualityProfile:
    id: str
    label: str
    kind: str                 # "video" | "audio"
    height: Optional[int] = None
    audio_codec: Optional[str] = None
    caption: str = ""


#: Ordered registry shown in the UI (segmented Video / Audio grids).
PROFILES: list[QualityProfile] = [
    QualityProfile("best",     "Best available", "video", None, None, "Top quality the site offers"),
    QualityProfile("2160p",    "4K · 2160p",      "video", 2160, None, "Ultra HD"),
    QualityProfile("1440p",    "QHD · 1440p",     "video", 1440, None, "Quad HD"),
    QualityProfile("1080p",    "1080p · Full HD", "video", 1080, None, "Great on any screen"),
    QualityProfile("720p",     "720p · HD",       "video", 720,  None, "Balanced"),
    QualityProfile("480p",     "480p",            "video", 480,  None, "Smaller files"),
    QualityProfile("360p",     "360p · Saver",    "video", 360,  None, "Data friendly"),
    QualityProfile("audio-mp3",  "MP3",           "audio", None, "mp3",  "320 kbps · plays everywhere"),
    QualityProfile("audio-m4a",  "M4A · AAC",     "audio", None, "m4a",  "256 kbps · Apple friendly"),
    QualityProfile("audio-opus", "Opus",          "audio", None, "opus", "Efficient, modern"),
    QualityProfile("audio-flac", "FLAC",          "audio", None, "flac", "Lossless compression"),
    QualityProfile("audio-wav",  "WAV",           "audio", None, "wav",  "Lossless PCM"),
]

_PROFILE_INDEX = {p.id: p for p in PROFILES}


def profile_by_id(profile_id: str | None) -> QualityProfile:
    return _PROFILE_INDEX.get(profile_id or "", PROFILES[0])


@dataclass
class JobOptions:
    """Snapshot of the advanced options a job was created with."""

    download_dir: str = ""
    organize: str = "none"            # none | site | type
    container: str = "mp4"            # mp4 | mkv | webm | original
    template: str = "%(title)s.%(ext)s"
    restrict_names: bool = False

    playlist_mode: str = "single"     # single | all | range
    playlist_range: str = ""

    subtitle_enabled: bool = False
    subtitle_langs: str = "en"
    subtitle_auto: bool = True
    subtitle_embed: bool = True

    embed_metadata: bool = True
    embed_thumbnail: bool = True
    sponsors_remove: bool = False
    use_archive: bool = False

    speed_limit_bytes: int = 0
    proxy: str = ""
    cookies_browser: str = ""
    cookies_file: str = ""
    concurrent_fragments: int = 4

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "JobOptions":
        valid = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in valid})


def default_options(download_dir: str = "") -> JobOptions:
    return JobOptions(download_dir=download_dir)


@dataclass
class DownloadJob:
    url: str
    profile_id: str = "best"
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: JobState = JobState.QUEUED
    title: Optional[str] = None
    uploader: Optional[str] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    webpage_url: Optional[str] = None
    site: str = ""

    total_bytes: Optional[int] = None
    downloaded_bytes: int = 0
    progress_percent: float = 0.0
    speed: Optional[float] = None
    eta: Optional[float] = None

    playlist_index: Optional[int] = None
    playlist_count: Optional[int] = None
    entry_title: Optional[str] = None

    output_path: Optional[str] = None
    error: Optional[str] = None

    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    options: JobOptions = field(default_factory=JobOptions)

    # --- transient (never serialized) ---
    cancel_event: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )
    worker_ref: Any = field(default=None, repr=False, compare=False)

    # ---------------------------------------------------------------- helpers
    @property
    def profile(self) -> QualityProfile:
        return profile_by_id(self.profile_id)

    @property
    def display_title(self) -> str:
        if self.entry_title:
            return self.entry_title
        return self.title or self.url

    def reset_for_retry(self) -> None:
        self.state = JobState.QUEUED
        self.error = None
        self.output_path = None
        self.completed_at = None
        self.downloaded_bytes = 0
        self.total_bytes = None
        self.progress_percent = 0.0
        self.speed = None
        self.eta = None
        self.cancel_event = threading.Event()

    def snapshot_fields(self) -> dict[str, Any]:
        """A thread-safe-ish copy of the fields the UI displays."""
        return {
            "job_id": self.job_id,
            "url": self.url,
            "profile_id": self.profile_id,
            "state": self.state.value,
            "title": self.title,
            "uploader": self.uploader,
            "duration": self.duration,
            "thumbnail_url": self.thumbnail_url,
            "site": self.site,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "progress_percent": self.progress_percent,
            "speed": self.speed,
            "eta": self.eta,
            "playlist_index": self.playlist_index,
            "playlist_count": self.playlist_count,
            "entry_title": self.entry_title,
            "output_path": self.output_path,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    def to_record(self) -> dict[str, Any]:
        """Serialization for history persistence."""
        rec = self.snapshot_fields()
        rec["profile_label"] = self.profile.label
        return rec

    @classmethod
    def from_record(cls, rec: dict[str, Any]) -> "DownloadJob":
        job = cls(url=rec.get("url", ""), profile_id=rec.get("profile_id", "best"))
        for key in (
            "job_id", "title", "uploader", "duration", "thumbnail_url", "site",
            "output_path", "error", "created_at", "completed_at", "webpage_url",
        ):
            value = rec.get(key)
            if value is not None:
                setattr(job, key, value)
        state_raw = rec.get("state")
        try:
            job.state = JobState(state_raw)
        except ValueError:
            job.state = JobState.COMPLETED
        opts = rec.get("options")
        if isinstance(opts, dict):
            job.options = JobOptions.from_dict(opts)
        return job
