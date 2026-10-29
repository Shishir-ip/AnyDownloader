"""History page: everything ever downloaded, searchable and re-runnable."""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from anydownloader.core import utils
from anydownloader.ui.context import AppContext
from anydownloader.ui.pages.base import Page
from anydownloader.ui.pages.queue_page import _reveal_in_explorer
from anydownloader.ui.widgets import (
    EmptyState, IconButton, SearchField, Segmented, ToggleSwitch, card, label,
    section_header,
)


class HistoryRow(QFrame):
    def __init__(self, record: dict, ctx: AppContext,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.record = record
        self.ctx = ctx
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 12, 10)
        root.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = label(record.get("title") or record.get("url") or "Untitled")
        f = title.font()
        f.setWeight(QFont.Weight.DemiBold)
        title.setFont(f)
        title.setWordWrap(False)
        fm = title.fontMetrics()
        title.setText(fm.elidedText(title.text(), Qt.TextElideMode.ElideRight, 640))
        text_col.addWidget(title)
        meta_bits = [record.get("site") or "Web", record.get("profile_label") or ""]
        ts = record.get("completed_at") or record.get("created_at")
        if ts:
            import time as _t
            meta_bits.append(_t.strftime("%Y-%m-%d %H:%M", _t.localtime(ts)))
        if record.get("output_path"):
            from pathlib import Path
            meta_bits.append(str(Path(record["output_path"]).parent))
        sub = label(" · ".join(b for b in meta_bits if b), "caption")
        sub.setWordWrap(False)
        fm2 = sub.fontMetrics()
        sub.setText(fm2.elidedText(sub.text(), Qt.TextElideMode.ElideRight, 640))
        text_col.addWidget(sub)
        root.addLayout(text_col, 1)

        if not ctx.history.exists_on_disk(record):
            missing = label("file moved", "caption")
            root.addWidget(missing)

        redownload = IconButton("retry", 15, "Download again")
        redownload.clicked.connect(self._redownload)
        root.addWidget(redownload)
        locate = IconButton("pin", 15, "Show in folder")
        locate.clicked.connect(self._locate)
        root.addWidget(locate)
        copy = IconButton("link", 15, "Copy link")
        copy.clicked.connect(self._copy)
        root.addWidget(copy)
        delete = IconButton("trash", 15, "Remove from history")
        delete.clicked.connect(self._delete)
        root.addWidget(delete)

    def _redownload(self) -> None:
        url = self.record.get("url")
        if not url:
            return
        self.ctx.manager.add_urls([url], self.record.get("profile_id"))
        if self.ctx.settings.auto_start:
            self.ctx.manager.start_all()
        self.ctx.notify("Re-added to the queue.", "success")
        self.ctx.switch_page("queue")

    def _locate(self) -> None:
        path = self.record.get("output_path")
        if path and os.path.isfile(path):
            _reveal_in_explorer(path)
        else:
            self.ctx.notify("That file is no longer on disk.", "warning")

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.record.get("url") or "")
        self.ctx.notify("Link copied.", "success")

    def _delete(self) -> None:
        self.ctx.history.delete(self.record.get("job_id") or "")
        self.hide()
        self.deleteLater()
        self.ctx.switch_page("history")  # cheap refresh


class HistoryPage(Page):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(ctx, "History", "Every download AnyDownloader has completed for you.",
                         scrollable=False, parent=parent)
        self._kind = "all"

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search = SearchField("Search history")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(lambda _t: self.reload())
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        kind_seg = Segmented()
        kind_seg.addSegment("All", "all")
        kind_seg.addSegment("Video", "video")
        kind_seg.addSegment("Audio", "audio")
        kind_seg.currentChanged.connect(self._on_kind)
        toolbar.addWidget(kind_seg)
        export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("secondary")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setFixedHeight(34)
        export_btn.clicked.connect(self._export)
        toolbar.addWidget(export_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondary")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(34)
        clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(clear_btn)
        self.add_body(self._wrap(toolbar))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.host = QWidget()
        self.col = QVBoxLayout(self.host)
        self.col.setContentsMargins(0, 0, 8, 8)
        self.col.setSpacing(8)
        self.col.addStretch(1)
        self.scroll.setWidget(self.host)
        self.add_body(self.scroll, 1)

        self.empty = EmptyState("history", "No history yet",
                                "Finished downloads will be listed here.")
        self.empty.hide()
        self.reload()

    def _wrap(self, lay) -> QWidget:
        w = QWidget()
        w.setLayout(lay)
        return w

    def _on_kind(self, kind: str) -> None:
        self._kind = kind
        self.reload()

    def showEvent(self, event) -> None:  # noqa: N801
        super().showEvent(event)
        self.reload()

    def reload(self) -> None:
        while self.col.count() > 1:
            item = self.col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        records = self.ctx.history.search(self.search.text(), self._kind)
        self.empty.setVisible(not records)
        for record in records[:300]:
            self.col.insertWidget(self.col.count() - 1, HistoryRow(record, self.ctx))

    def _export(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export history", "anydownloader-history.csv", "CSV files (*.csv)")
        if not dest:
            return
        count = self.ctx.history.export_csv(dest)
        self.ctx.notify(f"Exported {count} records.", "success")

    def _clear(self) -> None:
        self.ctx.history.clear()
        self.reload()
        self.ctx.notify("History cleared.", "info")
