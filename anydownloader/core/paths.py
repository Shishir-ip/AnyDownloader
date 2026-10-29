"""Filesystem locations, logging setup and frozen-app helpers."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from anydownloader import APP_NAME, __version__


def is_frozen() -> bool:
    """True when running from the PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def bundle_dir() -> Path:
    """Directory containing the app (or the PyInstaller extraction dir)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent.parent


def app_data_dir() -> Path:
    """Per-user writable data directory (settings, history, logs, archive)."""
    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        d = base / APP_NAME
    elif sys.platform == "darwin":
        d = home / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def history_path() -> Path:
    return app_data_dir() / "history.json"


def archive_path() -> Path:
    return app_data_dir() / "downloaded.txt"


def default_download_dir() -> Path:
    d = Path.home() / "Downloads" / APP_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path.home() / "Downloads"
    return d


def log_path() -> Path:
    return app_data_dir() / "logs"


def setup_logging(level: int = logging.INFO) -> None:
    """Rotating file log; console output only when debugging from source."""
    log_path().mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            log_path() / "anydownloader.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
    ]
    if not is_frozen() and os.environ.get("ANYDOWNLOADER_DEBUG"):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        handlers=handlers,
    )
    logging.getLogger("PyQt6").setLevel(logging.WARNING)
    logging.info("=== %s %s starting (frozen=%s) ===", APP_NAME, __version__, is_frozen())
