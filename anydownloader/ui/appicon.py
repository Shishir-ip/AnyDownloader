"""Programmatically drawn app icon (gradient tile + download arrow)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QConicalGradient, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

_cache: dict[int, QPixmap] = {}


def _draw(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    radius = size * 0.225
    path = QPainterPath()
    path.addRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), radius, radius)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#0A84FF"))
    grad.setColorAt(0.55, QColor("#5E5CE6"))
    grad.setColorAt(1.0, QColor("#AF52DE"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawPath(path)
    # soft top highlight
    highlight = QPainterPath()
    highlight.addRoundedRect(QRectF(size * 0.08, size * 0.05, size * 0.84, size * 0.4), radius * 0.8, radius * 0.8)
    p.setBrush(QColor(255, 255, 255, 26))
    p.drawPath(highlight)
    # white download arrow
    p.setBrush(QColor("#FFFFFF"))
    pen = QPen(QColor("#FFFFFF"), max(size * 0.055, 1.5))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    cx = size * 0.5
    shaft_top = size * 0.22
    arrow_y = size * 0.52
    p.drawLine(QPointF(cx, shaft_top), QPointF(cx, arrow_y))
    head = QPainterPath()
    head.moveTo(cx - size * 0.15, arrow_y - size * 0.10)
    head.lineTo(cx, arrow_y + size * 0.10)
    head.lineTo(cx + size * 0.15, arrow_y - size * 0.10)
    pen2 = QPen(QColor("#FFFFFF"), max(size * 0.055, 1.5))
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen2.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen2)
    p.drawPath(head)
    p.setPen(pen)
    p.drawLine(QPointF(size * 0.26, size * 0.72), QPointF(size * 0.74, size * 0.72))
    p.end()
    return pm


def pixmap(size: int = 256) -> QPixmap:
    if size not in _cache:
        _cache[size] = _draw(size)
    return _cache[size]


def icon() -> QIcon:
    ic = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(pixmap(size))
    return ic


# Sidebar badge: same tile, smaller — exposed for reuse
def badge_pixmap(size: int = 40) -> QPixmap:
    return pixmap(size)
