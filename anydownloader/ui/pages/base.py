"""Common page scaffolding: large-title header + scrollable body + flow layout."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLayout, QScrollArea, QVBoxLayout, QWidget,
)

from anydownloader.ui.context import AppContext
from anydownloader.ui.widgets import label


class Page(QFrame):
    """Base page: header with large title, optional trailing actions, scroll body."""

    def __init__(self, ctx: AppContext, title: str, subtitle: str = "",
                 scrollable: bool = True, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.title_label = label(title, "largeTitle")
        text_col.addWidget(self.title_label)
        if subtitle:
            sub = label(subtitle, "subtitle")
            text_col.addWidget(sub)
        header.addLayout(text_col, 1)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(8)
        header.addLayout(self.trailing)
        outer.addLayout(header)

        self.body_host = QWidget()
        self.body = QVBoxLayout(self.body_host)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(14)
        if scrollable:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(self.body_host)
            outer.addWidget(scroll, 1)
        else:
            outer.addWidget(self.body_host, 1)

    def add_body(self, widget: QWidget, stretch: int = 0) -> None:
        self.body.addWidget(widget, stretch)


class FlowLayout(QLayout):
    """Left-to-right wrap layout (Qt flow-layout pattern)."""

    def __init__(self, parent: Optional[QWidget] = None, margin: int = 0,
                 spacing: int = 8) -> None:
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self._items: list = []

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:  # noqa: N801
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N801
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N801
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N801
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:  # noqa: N801
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N801
        return self._do_layout(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N801
        super().setGeometry(rect)
        self._do_layout(rect, test=False)

    def sizeHint(self) -> QSize:  # noqa: N801
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N801
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(),
                                  -margins.right(), -margins.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()
