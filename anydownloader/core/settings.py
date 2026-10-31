"""User settings with JSON persistence and safe migration."""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field, fields
from typing import Any

from anydownloader.core import paths, utils

log = logging.getLogger(__name__)

VALID_THEMES = ("system", "light", "dark")
VALID_ORGANIZE = ("none", "site", "type")
VALID_CONTAINERS = ("mp4", "mkv", "webm", "original")
VALID_PLAYLIST_MODES = ("single", "all", "range")
VALID_BROWSERS = ("", "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium", "safari")

TEMPLATE_VARS_HELP = ", ".join(
    "%(" + v + ")s"
    for v in ("title", "id", "uploader", "extractor_key", "webpage_url_domain",
              "upload_date", "playlist_title", "playlist_index", "resolution", "ext")
)


@dataclass
class Settings:
    # Appearance
    theme: str = "system"          # system | light | dark
    accent: str = "blue"
    reduce_animations: bool = False

    # Downloads
    download_dir: str = ""
    organize: str = "none"         # none | site | type
    container: str = "mp4"
    template: str = "%(title)s.%(ext)s"
    restrict_names: bool = False
    default_profile: str = "1080p"

    # Queue behaviour
    max_concurrent: int = 2
    concurrent_fragments: int = 4
    speed_limit: str = ""          # human input, e.g. "5 MB/s"
    auto_start: bool = True
    clipboard_watch: bool = False
    notifications: bool = True
    minimize_to_tray: bool = False

    # Subtitles & metadata
    subtitle_enabled: bool = False
    subtitle_langs: str = "en"
    subtitle_auto: bool = True
    subtitle_embed: bool = True
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    embed_chapters: bool = True
    sponsors_remove: bool = False

    # Playlist
    playlist_mode: str = "single"
    playlist_range: str = "1-10"

    # Network
    proxy: str = ""
    cookies_browser: str = ""
    cookies_file: str = ""
    use_archive: bool = False

    # Updates
    check_updates_on_start: bool = True

    # Window state (not user-editable)
    window_geometry: str = ""
    _loaded: bool = field(default=False, repr=False)

    # ------------------------------------------------------------------ I/O
    def save(self) -> None:
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        try:
            path = paths.settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:  # pragma: no cover - disk issues
            log.error("Could not save settings: %s", exc)

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            raw = json.loads(paths.settings_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict):
            known = {f.name for f in fields(cls)}
            for key, value in raw.items():
                if key in known and not key.startswith("_"):
                    setattr(s, key, value)
        s.normalize()
        s._loaded = True
        return s

    def normalize(self) -> None:
        """Validate/repair every field (also used after UI edits)."""
        if self.theme not in VALID_THEMES:
            self.theme = "system"
        if self.organize not in VALID_ORGANIZE:
            self.organize = "none"
        if self.container not in VALID_CONTAINERS:
            self.container = "mp4"
        if self.playlist_mode not in VALID_PLAYLIST_MODES:
            self.playlist_mode = "single"
        if self.cookies_browser not in VALID_BROWSERS:
            self.cookies_browser = ""
        self.max_concurrent = utils.clamp(int(self.max_concurrent or 2), 1, 6)
        self.concurrent_fragments = utils.clamp(int(self.concurrent_fragments or 4), 1, 16)
        if not self.download_dir:
            self.download_dir = str(paths.default_download_dir())
        self.subtitle_langs = " ".join(
            part for part in self.subtitle_langs.replace(",", " ").split() if part
        )[:60] or "en"
        if utils.parse_rate_limit(self.speed_limit) is None:
            self.speed_limit = ""
        self.playlist_range = self.playlist_range.strip()[:40]
        self.template = self.template.strip()[:200] or "%(title)s.%(ext)s"

    # ------------------------------------------------------------- conveniences
    @property
    def speed_limit_bytes(self) -> int:
        return utils.parse_rate_limit(self.speed_limit) or 0

    def job_options(self) -> "JobOptions":
        """Snapshot current settings into per-job options."""
        from anydownloader.core.models import JobOptions
        return JobOptions(
            download_dir=self.download_dir,
            organize=self.organize,
            container=self.container,
            template=self.template,
            restrict_names=self.restrict_names,
            playlist_mode=self.playlist_mode,
            playlist_range=self.playlist_range,
            subtitle_enabled=self.subtitle_enabled,
            subtitle_langs=self.subtitle_langs,
            subtitle_auto=self.subtitle_auto,
            subtitle_embed=self.subtitle_embed,
            embed_metadata=self.embed_metadata,
            embed_thumbnail=self.embed_thumbnail,
            sponsors_remove=self.sponsors_remove,
            use_archive=self.use_archive,
            speed_limit_bytes=self.speed_limit_bytes,
            proxy=self.proxy.strip(),
            cookies_browser=self.cookies_browser,
            cookies_file=self.cookies_file.strip(),
            concurrent_fragments=self.concurrent_fragments,
        )


class SettingsChangeNotifier:
    """Tiny observer so UI pieces can react to live setting changes."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callbacks: dict[int, Any] = {}
        self._next = 0

    def subscribe(self, cb: Any) -> int:
        with self._lock:
            self._next += 1
            self._callbacks[self._next] = cb
            return self._next

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._callbacks.pop(token, None)

    def emit(self, settings: Settings, changed_key: str | None = None) -> None:
        with self._lock:
            cbs = list(self._callbacks.values())
        for cb in cbs:
            try:
                cb(settings, changed_key)
            except Exception:  # pragma: no cover - defensive
                log.exception("settings callback failed")
