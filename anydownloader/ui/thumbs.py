"""Async thumbnail loading with an in-memory cache and rounded rendering."""
from __future__ import annotations

import logging

from PySide6.QtCore import QBuffer, QIODevice, QObject, QThreadPool, QRunnable, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap, QColor, Qt
from PySide6.QtCore import QRectF

log = logging.getLogger(__name__)


def rounded_pixmap(source: QPixmap, width: int, height: int, radius: int = 8) -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(path)
    scaled = source.scaled(
        width, height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (scaled.width() - width) / 2
    y = (scaled.height() - height) / 2
    painter.drawPixmap(int(-x), int(-y), scaled)
    painter.end()
    return pm


def placeholder_pixmap(width: int, height: int, radius: int = 8, color: str = "#C7C7CC") -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(path)
    painter.fillRect(0, 0, width, height, QColor(color))
    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setPointSizeF(height * 0.34)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, "▶")
    painter.end()
    return pm


class _Fetch(QRunnable):
    def __init__(self, loader: "ThumbnailLoader", url: str) -> None:
        super().__init__()
        self.loader = loader
        self.url = url

    def run(self) -> None:
        import urllib.request

        pixmap: QPixmap | None = None
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "AnyDownloader"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read(5_000_000)
            image = QImage()
            if image.loadFromData(data):
                pixmap = QPixmap.fromImage(image)
        except Exception:
            log.debug("thumbnail fetch failed: %s", self.url)
        self.loader._deliver(self.url, pixmap)


class ThumbnailLoader(QObject):
    """Downloads thumbnails off-thread; emits (url, QPixmap|None)."""

    loaded = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cache: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._order: list[str] = []

    def _deliver(self, url: str, pixmap: QPixmap | None) -> None:
        self._pending.discard(url)
        if pixmap is not None:
            self._cache[url] = pixmap
            self._order.append(url)
            while len(self._order) > 120:
                self._cache.pop(self._order.pop(0), None)
        self.loaded.emit(url, pixmap)

    def get(self, url: str) -> None:
        """Request a thumbnail; `loaded` fires on the GUI thread."""
        if not url or url in self._pending or url in self._cache:
            if url in self._cache:
                self.loaded.emit(url, self._cache[url])
            elif not url:
                self.loaded.emit(url, None)
            return
        self._pending.add(url)
        QThreadPool.globalInstance().start(_Fetch(self, url))

    def cached(self, url: str) -> QPixmap | None:
        return self._cache.get(url)
