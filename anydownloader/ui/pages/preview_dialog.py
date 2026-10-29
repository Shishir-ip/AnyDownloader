"""Metadata preview sheet shown by 'Fetch info'."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from anydownloader.core import utils
from anydownloader.ui.context import AppContext
from anydownloader.ui.thumbs import placeholder_pixmap, rounded_pixmap
from anydownloader.ui.widgets import EmptyState, PillBadge, label, section_header


class PreviewDialog(QDialog):
    def __init__(self, info: dict, ctx: AppContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.info = info
        self.setWindowTitle("Link preview")
        self.setModal(True)
        self.setMinimumSize(560, 420)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(14)
        self.thumb = QLabel()
        self.thumb.setFixedSize(192, 108)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb.setPixmap(placeholder_pixmap(192, 108))
        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        title = label(info.get("title") or "Untitled", "title")
        title.setWordWrap(True)
        text_col.addWidget(title)
        bits = []
        if info.get("uploader"):
            bits.append(str(info["uploader"]))
        if info.get("duration"):
            bits.append(utils.human_duration(float(info["duration"])))
        if info.get("view_count"):
            try:
                bits.append(f"{int(info['view_count']):,} views")
            except (TypeError, ValueError):
                pass
        if info.get("upload_date"):
            d = str(info["upload_date"])
            bits.append(f"{d[0:4]}-{d[4:6]}-{d[6:8]}")
        meta_line = label(" · ".join(bits) or info.get("extractor", ""), "subtitle")
        meta_line.setWordWrap(True)
        text_col.addWidget(meta_line)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        if info.get("is_playlist"):
            count = info.get("entry_count")
            chips.addWidget(PillBadge(f"Playlist · {count} items" if count else "Playlist", "info"))
        chips.addWidget(PillBadge(str(info.get("extractor") or "Web"), "neutral"))
        chips.addStretch(1)
        text_col.addLayout(chips)
        text_col.addStretch(1)
        head.addWidget(self.thumb)
        head.addLayout(text_col, 1)
        root.addLayout(head)

        if info.get("thumbnail"):
            ctx.thumbnail_loader.loaded.connect(self._on_thumb)
            ctx.thumbnail_loader.get(str(info["thumbnail"]))

        if info.get("formats"):
            fmt_title = section_header("Available qualities")
            root.addWidget(fmt_title)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setFixedHeight(190)
            host = QWidget()
            col = QVBoxLayout(host)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(4)
            for fmt in info["formats"]:
                row = QHBoxLayout()
                name = label(f"{fmt['label']} · {str(fmt['ext']).upper()}")
                row.addWidget(name, 1)
                if fmt.get("hdr"):
                    row.addWidget(PillBadge("HDR", "info"))
                row.addWidget(label(utils.human_size(fmt.get("size")), "subtitle"))
                col.addLayout(row)
            col.addStretch(1)
            scroll.setWidget(host)
            root.addWidget(scroll)
        elif info.get("is_playlist") and info.get("entries"):
            fmt_title = section_header("First entries")
            root.addWidget(fmt_title)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setFixedHeight(190)
            host = QWidget()
            col = QVBoxLayout(host)
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(2)
            for entry in info["entries"][:30]:
                row = QHBoxLayout()
                t = label(entry.get("title") or entry.get("url") or "—")
                row.addWidget(t, 1)
                row.addWidget(label(utils.human_duration(entry.get("duration")), "subtitle"))
                col.addLayout(row)
            col.addStretch(1)
            scroll.setWidget(host)
            root.addWidget(scroll)

        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Close")
        cancel.setObjectName("secondary")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        add_btn = QPushButton("Add to Queue")
        add_btn.setObjectName("primary")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(38)
        add_btn.clicked.connect(self._add)
        buttons.addWidget(add_btn)
        root.addLayout(buttons)

    def _on_thumb(self, url: str, pixmap) -> None:
        if pixmap is None or url != self.info.get("thumbnail"):
            return
        self.thumb.setPixmap(rounded_pixmap(QPixmap(pixmap), 192, 108, 10))

    def _add(self) -> None:
        url = self.info.get("webpage_url") or ""
        if not url:
            return
        self.ctx.manager.add_urls([url], self.ctx.settings.default_profile)
        if self.ctx.settings.auto_start:
            self.ctx.manager.start_all()
        self.ctx.notify("Added to queue.", "success")
        self.accept()
        self.ctx.switch_page("queue")
