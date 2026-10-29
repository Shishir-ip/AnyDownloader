"""Shared application context passed to all pages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from PySide6.QtCore import QObject

from anydownloader.core.history import History
from anydownloader.core.manager import DownloadManager
from anydownloader.core.settings import Settings
from anydownloader.ui.thumbs import ThumbnailLoader


@dataclass
class AppContext:
    settings: Settings
    manager: DownloadManager
    history: History
    thumbnail_loader: ThumbnailLoader
    switch_page: Callable[[str], None] = lambda name: None
    notify: Callable[[str, str], None] = lambda text, kind: None
    window: Optional[QObject] = None
    request_quit_minimize: Callable[[], None] = lambda: None
