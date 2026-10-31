"""Custom-painted widgets that give AnyDownloader its Apple-flavoured feel."""
from __future__ import annotations

import time
import weakref
from typing import Any, Callable, Optional

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPointF, QRectF, QPropertyAnimation, QRect,
    QSize, Qt, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton, QButtonGroup, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout,
    QWidget,
)

from anydownloader.ui import icons
from anydownloader.ui.theme import ThemeManager, current_palette, mix, alpha


def _register(widget: QWidget) -> None:
    mgr = ThemeManager._instance
    if mgr is not None:
        mgr.register_painted(widget)


def _reduce_animations() -> bool:
    mgr = ThemeManager._instance
    return bool(mgr and mgr.reduce_animations)


def set_role(widget: QWidget, role: str) -> None:
    widget.setProperty("role", role)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def label(text: str, role: str = "") -> QLabel:
    lbl = QLabel(text)
    if role:
        set_role(lbl, role)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return lbl


def card(margins=(16, 14, 16, 16), spacing=10) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return frame, lay


class IconGlyph(QWidget):
    """Theme-aware icon painted at any size."""

    def __init__(self, name: str, size: int = 20, color: Optional[str] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._size = size
        self._color = color  # None → label color / accent
        self.setFixedSize(size + 2, size + 2)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        _register(self)

    def set_icon_name(self, name: str) -> None:
        self._name = name
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._size + 2, self._size + 2)

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        color = self._color
        if color is None:
            color = p.label
        elif color == "accent":
            color = p.accent
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pm = icons.pixmap(self._name, color, self._size)
        x = (self.width() - self._size) / 2
        y = (self.height() - self._size) / 2
        painter.drawPixmap(QPointF(x, y), pm)


# ============================================================== ToggleSwitch
class ToggleSwitch(QAbstractButton):
    """iOS-style animated switch."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        _register(self)

    def _on_anim(self, value: float) -> None:
        self._pos = value
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(51, 31)

    def resizeEvent(self, event) -> None:  # noqa: N801
        self.setFixedSize(51, 31)

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_off = "#E9E9EA" if p.name == "light" else "#39393D"
        track_color = QColor(track_off)
        if self._pos > 0:
            track_color = QColor(mix(track_off, p.accent, self._pos))
        if not self.isEnabled():
            painter.setOpacity(0.4)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, 50, 30), 15.0, 15.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawPath(path)
        thumb_d = 27.0
        x = 2.0 + self._pos * (51.0 - 2 * 2 - thumb_d)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(x, (31 - thumb_d) / 2, thumb_d, thumb_d))

    def nextCheckState(self) -> None:  # noqa: N801
        self.setChecked(not self.isChecked())

    def setChecked(self, checked: bool) -> None:  # noqa: N801
        super().setChecked(checked)
        self._animate_to(1.0 if checked else 0.0)

    def _animate_to(self, target: float) -> None:
        if _reduce_animations():
            self._pos = target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(target)
        self._anim.start()


# ================================================================= Segmented
class Segmented(QFrame):
    """iOS segmented control with an animated selection pill."""

    currentChanged = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._buttons: list[QPushButton] = []
        self._keys: list[str] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._pill = QRectF(0, 0, 0, 0)
        self._pill_anim = QVariantAnimation(self)
        self._pill_anim.setDuration(220)
        self._pill_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pill_anim.valueChanged.connect(self._on_pill)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(0)
        self._lay = lay
        self.setMinimumHeight(36)
        _register(self)

    def _on_pill(self, value: QRect) -> None:
        self._pill = QRectF(value)
        self.update()

    def addSegment(self, text: str, key: str) -> None:
        btn = QPushButton(text)
        btn.setObjectName("segButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        btn.clicked.connect(lambda _=False, k=key: self.setCurrent(k))
        self._lay.addWidget(btn)
        self._group.addButton(btn)
        self._buttons.append(btn)
        self._keys.append(key)
        if len(self._buttons) == 1:
            btn.setChecked(True)
            QTimer.singleShot(0, lambda: self._snap_pill())

    def setCurrent(self, key: str, animate: bool = True) -> None:
        if key not in self._keys:
            return
        idx = self._keys.index(key)
        btn = self._buttons[idx]
        if not btn.isChecked():
            btn.setChecked(True)
        if animate and not _reduce_animations():
            start = QRect(int(self._pill.x()), int(self._pill.y()),
                          int(self._pill.width()), int(self._pill.height()))
            self._pill_anim.stop()
            self._pill_anim.setStartValue(start)
            self._pill_anim.setEndValue(QRect(btn.geometry()))
            self._pill_anim.start()
        else:
            self._snap_pill()
        self.currentChanged.emit(key)

    def current(self) -> str:
        for btn, key in zip(self._buttons, self._keys):
            if btn.isChecked():
                return key
        return self._keys[0] if self._keys else ""

    def _snap_pill(self) -> None:
        for btn in self._buttons:
            if btn.isChecked():
                self._pill = QRectF(btn.geometry())
                self.update()
                return

    def paintEvent(self, event) -> None:  # noqa: N801
        if self._pill.width() <= 0:
            self._snap_pill()
            return
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.fill))
        painter.drawPath(path)
        pill = QPainterPath()
        pill.addRoundedRect(self._pill, 8, 8)
        painter.setBrush(QColor(p.card))
        painter.drawPath(pill)


# =========================================================== SmoothProgressBar
class SmoothProgressBar(QWidget):
    """Progress bar whose displayed value eases toward the target (iOS-like)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._shown = 0.0
        self._target = 0.0
        self._indeterminate = False
        self._sweep = 0.0
        self.setFixedHeight(6)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_value)
        self._sweep_anim = QVariantAnimation(self)
        self._sweep_anim.setStartValue(0.0)
        self._sweep_anim.setEndValue(1.0)
        self._sweep_anim.setDuration(1250)
        self._sweep_anim.setLoopCount(-1)
        self._sweep_anim.valueChanged.connect(self._on_sweep)
        _register(self)

    def _on_value(self, v: float) -> None:
        self._shown = v
        self.update()

    def _on_sweep(self, v: float) -> None:
        self._sweep = v
        self.update()

    def set_value(self, percent: float) -> None:
        self._target = max(0.0, min(100.0, percent))
        if self._indeterminate:
            return
        if _reduce_animations():
            self._shown = self._target
            self.update()
            return
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(self._target)
        self._anim.start()

    def set_indeterminate(self, on: bool) -> None:
        if on == self._indeterminate:
            return
        self._indeterminate = on
        if on:
            self._sweep_anim.start()
        else:
            self._sweep_anim.stop()
            self.set_value(self._target)

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = float(self.height())
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, float(self.width()), h), h / 2, h / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p.fill_hover))
        painter.drawPath(path)
        fill = QPainterPath()
        if self._indeterminate:
            w = self.width() * 0.32
            x = (self.width() - w) * self._sweep
            # ease in-out ping-pong
            t = self._sweep
            x = (self.width() + w) * t - w
            fill.addRoundedRect(QRectF(x, 0, w, h), h / 2, h / 2)
            painter.setBrush(QColor(p.accent))
            painter.drawPath(fill)
            return
        if self._shown <= 0.01:
            return
        w = self.width() * (self._shown / 100.0)
        fill.addRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        painter.setBrush(QColor(p.accent))
        painter.drawPath(fill)


# =============================================================== ProgressRing
class ProgressRing(QWidget):
    """Small indeterminate spinner (shared timer across instances)."""

    _rings: "weakref.WeakSet[ProgressRing]" = weakref.WeakSet()
    _timer: Optional[QTimer] = None
    _t0 = time.monotonic()

    def __init__(self, size: int = 22, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        ProgressRing._rings.add(self)
        self._ensure_timer()
        _register(self)

    @classmethod
    def _ensure_timer(cls) -> None:
        if ProgressRing._timer is None:
            timer = QTimer()
            timer.setInterval(33)
            timer.timeout.connect(ProgressRing._tick)
            ProgressRing._timer = timer
        if not ProgressRing._timer.isActive():
            ProgressRing._timer.start()

    @classmethod
    def _tick(cls) -> None:
        alive = False
        for ring in list(cls._rings):
            if ring.isVisible():
                ring.update()
                alive = True
        if not alive and cls._timer:
            cls._timer.stop()

    def showEvent(self, event) -> None:  # noqa: N801
        super().showEvent(event)
        self._ensure_timer()

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        angle = (time.monotonic() - ProgressRing._t0) * 300 % 360
        rect = QRectF(2.5, 2.5, self._size - 5, self._size - 5)
        pen = painter.pen()
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setColor(QColor(alpha(p.accent, 0.25)))
        pen.setWidthF(2.4)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)
        pen.setColor(QColor(p.accent))
        painter.setPen(pen)
        painter.drawArc(rect, int(-angle * 16), 100 * 16)


# ================================================================= IconButton
class IconButton(QPushButton):
    """Borderless icon button with hover fill; theme-aware."""

    def __init__(self, name: str, size: int = 17, tooltip: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._name = name
        self._size = size
        self._color: Optional[str] = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("iconButton")
        pad = 6
        self.setFixedSize(size + 2 * pad + 2, size + 2 * pad + 2)
        if tooltip:
            self.setToolTip(tooltip)
        _register(self)

    def set_icon_name(self, name: str) -> None:
        self._name = name
        self.update()

    def set_color(self, color: Optional[str]) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = 9.0
        if self.isDown():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.fill_hover))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), radius, radius)
        elif self.underMouse():
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.fill))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), radius, radius)
        color = self._color or (p.accent if self.property("accent") else p.label)
        if not self.isEnabled():
            painter.setOpacity(0.35)
        pm = icons.pixmap(self._name, color, self._size)
        x = (self.width() - self._size) / 2
        y = (self.height() - self._size) / 2
        painter.drawPixmap(QPointF(x, y), pm)


# ================================================================== NavButton
class NavButton(QPushButton):
    """Sidebar navigation item: icon + label, animated selection."""

    def __init__(self, icon_name: str, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._icon = icon_name
        self._text = text
        self.setCheckable(True)
        self.setObjectName("navButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hover = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(120)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self.setFont(QFont(self.font().family(), -1, QFont.Weight.DemiBold))
        _register(self)

    def _on_hover(self, v: float) -> None:
        self._hover = v
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N801
        super().enterEvent(event)
        self._anim_hover(1.0)

    def leaveEvent(self, event) -> None:  # noqa: N801
        super().leaveEvent(event)
        self._anim_hover(0.0)

    def _anim_hover(self, target: float) -> None:
        if _reduce_animations():
            self._hover = target
            self.update()
            return
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        selected = self.isChecked()
        painter.setPen(Qt.PenStyle.NoPen)
        if selected:
            path = QPainterPath()
            path.addRoundedRect(rect, 9, 9)
            painter.setBrush(QColor(p.accent_soft))
            painter.drawPath(path)
        elif self._hover > 0:
            painter.setOpacity(self._hover)
            path = QPainterPath()
            path.addRoundedRect(rect, 9, 9)
            painter.setBrush(QColor(alpha(p.label, 0.06)))
            painter.drawPath(path)
            painter.setOpacity(1.0)
        color = p.accent if selected else p.label
        pm = icons.pixmap(self._icon, color, 18)
        icon_y = (self.height() - 18) / 2
        painter.drawPixmap(QPointF(12, icon_y), pm)
        painter.setPen(QColor(color))
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold)
        font.setPointSizeF(10.5)
        painter.setFont(font)
        painter.drawText(QPointF(44, self.height() / 2 + 4.5), self._text)


# =============================================================== QualityCard
class QualityCard(QAbstractButton):
    """Checkable quality preset card with iOS-style selection."""

    def __init__(self, title: str, caption: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._title = title
        self._caption = caption
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._hover = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(120)
        self._hover_anim.valueChanged.connect(lambda v: (setattr(self, "_hover", v), self.update()))
        _register(self)

    def enterEvent(self, event) -> None:  # noqa: N801
        super().enterEvent(event)
        if not _reduce_animations():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        else:
            self._hover = 1.0
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N801
        super().leaveEvent(event)
        if not _reduce_animations():
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(0.0)
            self._hover_anim.start()
        else:
            self._hover = 0.0
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)
        selected = self.isChecked()
        bg = QColor(p.card if selected else mix(p.fill, p.fill_hover, self._hover * 0.6))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawPath(path)
        if selected:
            painter.setPen(QColor(p.accent))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = painter.pen()
            pen.setWidthF(2.0)
            painter.setPen(pen)
            path2 = QPainterPath()
            path2.addRoundedRect(rect.adjusted(1, 1, -1, -1), 13, 13)
            painter.drawPath(path2)
        title_font = QFont(self.font())
        title_font.setPointSizeF(10.5)
        title_font.setWeight(QFont.Weight.DemiBold)
        caption_font = QFont(self.font())
        caption_font.setPointSizeF(8.2)
        painter.setFont(title_font)
        painter.setPen(QColor(p.label))
        painter.drawText(QPointF(14, 27), self._title)
        painter.setFont(caption_font)
        painter.setPen(QColor(p.tertiary))
        fm = QFontMetrics(caption_font)
        elided = fm.elidedText(self._caption, Qt.TextElideMode.ElideRight, int(self.width() - 64))
        painter.drawText(QPointF(14, 45), elided)
        # selection bubble
        if selected:
            d = 18.0
            cx = self.width() - d - 12
            cy = 12
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(p.accent))
            painter.drawEllipse(QRectF(cx, cy, d, d))
            check = icons.pixmap("check", "#FFFFFF", 11)
            painter.drawPixmap(QPointF(cx + (d - 11) / 2, cy + (d - 11) / 2), check)


# =================================================================== PillBadge
class PillBadge(QWidget):
    """Coloured state chip (Completed / Failed / …)."""

    KIND_COLORS = {
        "success": ("green", "Completed"),
        "error": ("red", "Failed"),
        "warning": ("orange", " "),
        "info": ("accent", "Downloading"),
        "neutral": ("tertiary", "Queued"),
    }

    def __init__(self, text: str = "", kind: str = "neutral",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._kind = kind
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._update_size()
        _register(self)

    def set_kind(self, kind: str, text: Optional[str] = None) -> None:
        self._kind = kind
        if text is not None:
            self._text = text
        self._update_size()
        self.update()

    def _color(self) -> tuple[QColor, QColor]:
        p = current_palette()
        key = self.KIND_COLORS.get(self._kind, ("tertiary", ""))[0]
        base = {
            "green": p.green, "red": p.red, "orange": p.orange,
            "accent": p.accent, "tertiary": p.tertiary,
        }[key]
        return QColor(base), QColor(p.label)

    def _update_size(self) -> None:
        font = QFont(self.font())
        font.setPointSizeF(8.5)
        font.setWeight(QFont.Weight.DemiBold)
        fm = QFontMetrics(font)
        width = fm.horizontalAdvance(self._text) + 22
        self.setFixedSize(max(width, 34), 21)

    def paintEvent(self, event) -> None:  # noqa: N801
        color, text_color = self._color()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(alpha(color.name(), 0.16)))
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                            self.height() / 2, self.height() / 2)
        painter.drawPath(path)
        font = QFont(self.font())
        font.setPointSizeF(8.5)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self._text)


# ======================================================================= Toast
class Toast(QFrame):
    """One toast notification."""

    closed = Signal(object)

    def __init__(self, text: str, kind: str = "info", action_text: str = "",
                 on_action: Optional[Callable[[], None]] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._text = text
        self._kind = kind
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 12, 8)
        lay.setSpacing(10)
        p = current_palette()
        icon_name = {"success": "check", "error": "warning", "warning": "warning",
                     "info": "info"}.get(kind, "info")
        icon_color = {"success": p.green, "error": p.red, "warning": p.orange,
                      "info": p.accent}.get(kind, p.accent)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, icon_color, 18))
        glyph.setFixedSize(18, 18)
        lay.addWidget(glyph)
        text_label = label(text)
        text_label.setWordWrap(False)
        lay.addWidget(text_label, 1)
        if action_text:
            action_btn = QPushButton(action_text)
            action_btn.setObjectName("secondary")
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setFixedHeight(30)

            def _do_action() -> None:
                if on_action:
                    on_action()
                self.dismiss()

            action_btn.clicked.connect(_do_action)
            lay.addWidget(action_btn)
        close_btn = IconButton("x", 14, "Dismiss")
        close_btn.clicked.connect(self.dismiss)
        lay.addWidget(close_btn)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._fade_in = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_in.setDuration(200)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(240)
        self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)

    def start(self, start_pos: QPoint, final_pos: QPoint) -> None:
        self.move(start_pos)
        self.show()
        if _reduce_animations():
            self._effect.setOpacity(1.0)
            self.move(final_pos)
            return
        self._slide.setStartValue(start_pos)
        self._slide.setEndValue(final_pos)
        self._slide.start()
        self._fade_in.start()

    def dismiss(self) -> None:
        fade = QPropertyAnimation(self._effect, b"opacity", self)
        fade.setDuration(160)
        fade.setStartValue(self._effect.opacity())
        fade.setEndValue(0.0)
        fade.finished.connect(self._finish)
        fade.start()
        self._fade_out_anim = fade

    def _finish(self) -> None:
        self.closed.emit(self)
        self.deleteLater()

    def paintEvent(self, event) -> None:  # noqa: N801
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 13, 13)
        painter.setPen(QColor(p.separator))
        painter.setBrush(QColor(p.elevated))
        painter.drawPath(path)


class ToastHost(QWidget):
    """Positions and stacks toasts at the bottom-centre of the window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._toasts: list[Toast] = []
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

    def show_toast(self, text: str, kind: str = "info", action_text: str = "",
                   on_action: Optional[Callable[[], None]] = None,
                   duration_ms: int = 4000) -> Toast:
        toast = Toast(text, kind, action_text, on_action, self)
        toast.closed.connect(self._on_closed)
        self._toasts.append(toast)
        toast.adjustSize()
        if len(self._toasts) > 3:
            self._toasts[0].dismiss()
        QTimer.singleShot(duration_ms, toast.dismiss)
        toast.show()
        toast.adjustSize()
        self._relayout(animate_new=toast)
        return toast

    def _on_closed(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._relayout()

    def _relayout(self, animate_new: Optional[Toast] = None) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        y = parent.height() - 24
        for toast in reversed(self._toasts):
            toast.adjustSize()
            width = min(toast.width(), parent.width() - 60)
            toast.setFixedWidth(width)
            x = (parent.width() - width) / 2
            final = QPoint(int(x), int(y - toast.height()))
            if toast is animate_new:
                start = QPoint(final.x(), final.y() + 16)
                toast.start(start, final)
            else:
                toast.move(final)
            y = final.y() - 8


# ============================================================ AnimatedSection
class AnimatedSection(QWidget):
    """Expanding/collapsing card used for the advanced options panel."""

    def __init__(self, title: str, content: QWidget,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._expanded = False
        self._chevron_angle = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.header = QPushButton(title)
        self.header.setObjectName("secondary")
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.setFixedHeight(38)
        self.header.clicked.connect(self.toggle)
        layout.addWidget(self.header)
        self._content = content
        content.setMaximumHeight(0)
        layout.addWidget(content)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        _register(self)

    def _on_anim(self, v: float) -> None:
        target = self._target_height
        self._content.setMaximumHeight(int(v * target))
        self._chevron_angle = v * 180.0
        self.update()

    @property
    def _target_height(self) -> int:
        hint = self._content.layout().minimumSize() if self._content.layout() else QSize()
        return max(hint.height() + 6, 40)

    def toggle(self) -> None:
        self._expanded = not self._expanded
        if _reduce_animations():
            self._content.setMaximumHeight(self._target_height if self._expanded else 0)
            self._chevron_angle = 180.0 if self._expanded else 0.0
        else:
            self._anim.stop()
            self._anim.setStartValue(self._chevron_angle / 180.0)
            self._anim.setEndValue(1.0 if self._expanded else 0.0)
            self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N801 - header chevron handled via QSS
        return super().paintEvent(event)


# ============================================================= FadeSlideStack
class FadeSlideStack(QStackedWidget):
    """Page stack. Page-crossfade via QGraphicsOpacityEffect proved unreliable
    (black-page artifacts), so switching is instant — the app's motion design
    lives in the controls instead."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)


# ================================================================ EmptyState
class EmptyState(QWidget):
    def __init__(self, icon_name: str, title: str, caption: str,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 40, 30, 40)
        lay.setSpacing(6)
        lay.addStretch(1)
        glyph = IconGlyph(icon_name, 46)
        self._glyph = glyph
        lay.addWidget(glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        title_label = label(title, "title")
        title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        caption_label = label(caption, "subtitle")
        caption_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        caption_label.setWordWrap(True)
        lay.addWidget(title_label)
        lay.addWidget(caption_label)
        lay.addStretch(1)


# ================================================================ SearchField
class SearchField(QLineEdit):
    def __init__(self, placeholder: str = "Search", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(36)
        self.setTextMargins(32, 0, 8, 0)
        self.setClearButtonEnabled(True)
        _register(self)

    def paintEvent(self, event) -> None:  # noqa: N801
        super().paintEvent(event)
        p = current_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pm = icons.pixmap("search", p.tertiary, 15)
        painter.drawPixmap(QPointF(10, (self.height() - 15) / 2), pm)


# ============================================================ SectionHeader
def section_header(text: str, parent: Optional[QWidget] = None) -> QLabel:
    lbl = label(text.upper(), "sectionTitle")
    lbl.setContentsMargins(4, 0, 0, 0)
    return lbl


def key_value_row(icon_name: str, title: str, caption: str = "",
                  control: Optional[QWidget] = None) -> QWidget:
    """iOS settings-style row: icon | title+caption | trailing control."""
    row = QWidget()
    row.setObjectName("settingsRow")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(12)
    glyph = IconGlyph(icon_name, 20)
    glyph._color = "accent"
    lay.addWidget(glyph)
    text_col = QVBoxLayout()
    text_col.setSpacing(1)
    text_col.addWidget(label(title))
    if caption:
        cap = label(caption, "caption")
        cap.setWordWrap(True)
        text_col.addWidget(cap)
    lay.addLayout(text_col, 1)
    if control is not None:
        control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return row
