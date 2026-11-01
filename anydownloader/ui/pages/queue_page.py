"""Queue page: live cards for every download with progress and actions."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from anydownloader.core import utils
from anydownloader.core.models import DownloadJob, JobState, STATE_LABEL
from anydownloader.ui.context import AppContext
from anydownloader.ui.pages.base import Page
from anydownloader.ui.thumbs import placeholder_pixmap, rounded_pixmap
from anydownloader.ui.widgets import (
    EmptyState, IconButton, PillBadge, SmoothProgressBar, card, label,
    section_header,
)

THUMB_W, THUMB_H = 112, 64


def _reveal_in_explorer(path: str) -> None:
    if not path:
        return
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])  # noqa: S603,S607
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])  # noqa: S603,S607
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])  # noqa: S603,S607


class JobCard(QFrame):
    """One download in the list."""

    actionRequested = Signal(str, str)  # job_id, action

    def __init__(self, job: DownloadJob, ctx: AppContext,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.job = job
        self.ctx = ctx
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(THUMB_W, THUMB_H)
        self.thumb_label.setPixmap(placeholder_pixmap(THUMB_W, THUMB_H))
        top.addWidget(self.thumb_label)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.title_label = label(job.display_title, "")
        self.title_label.setProperty("role", "title")
        font = self.title_label.font()
        font.setPointSizeF(11)
        font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(font)
        self.title_label.setWordWrap(False)
        info_col.addWidget(self.title_label)
        self.meta_label = label("", "caption")
        info_col.addWidget(self.meta_label)
        self.error_label = label("", "caption")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        info_col.addWidget(self.error_label)
        top.addLayout(info_col, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)
        self.badge = PillBadge("", "neutral")
        right_col.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignRight)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(2)
        self.actions.addStretch(1)
        right_col.addLayout(self.actions)
        top.addLayout(right_col)
        root.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.progress = SmoothProgressBar()
        bottom.addWidget(self.progress, 1)
        self.percent_label = label("", "")
        pf = self.percent_label.font()
        pf.setPointSizeF(9.5)
        pf.setWeight(QFont.Weight.DemiBold)
        self.percent_label.setFont(pf)
        self.percent_label.setFixedWidth(52)
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bottom.addWidget(self.percent_label)
        root.addLayout(bottom)

        self._buttons: dict[str, IconButton] = {}
        self._action_buttons()
        self.refresh(job)

    # ------------------------------------------------------------------ ui
    def _make_button(self, action: str, icon: str, tooltip: str) -> None:
        btn = IconButton(icon, 15, tooltip)
        btn.clicked.connect(lambda: self.actionRequested.emit(self.job.job_id, action))
        self.actions.insertWidget(self.actions.count() - 1, btn)
        self._buttons[action] = btn

    def _action_buttons(self) -> None:
        for btn in self._buttons.values():
            btn.setParent(None)
            btn.deleteLater()
        self._buttons.clear()
        state = self.job.state
        if state is JobState.DOWNLOADING or state is JobState.POSTPROCESSING:
            self._make_button("cancel", "stop", "Stop (partial file is kept)")
        elif state is JobState.QUEUED:
            self._make_button("cancel", "x", "Remove from queue")
        elif state is JobState.FAILED:
            self._make_button("retry", "retry", "Retry")
            self._make_button("remove", "trash", "Remove")
        elif state is JobState.CANCELLED:
            self._make_button("retry", "retry", "Download again")
            self._make_button("remove", "trash", "Remove")
        elif state is JobState.COMPLETED:
            if self.job.output_path:
                self._make_button("locate", "pin", "Show in folder")
                self._make_button("open", "play", "Open file")
            self._make_button("again", "retry", "Download again")
            self._make_button("remove", "trash", "Remove")
        self._make_button("copy", "link", "Copy link")

    # --------------------------------------------------------------- update
    def refresh(self, job: DownloadJob) -> None:
        self.job = job
        state = job.state
        title = job.display_title
        fm = self.title_label.fontMetrics()
        self.title_label.setText(fm.elidedText(title, Qt.TextElideMode.ElideRight,
                                               max(120, self.title_label.width() or 400)))

        meta_bits = [job.site or "Web", job.profile.label]
        if job.duration:
            meta_bits.append(utils.human_duration(job.duration))
        if job.total_bytes:
            meta_bits.append(utils.human_size(job.total_bytes))
        if job.playlist_count:
            meta_bits.append(f"playlist {job.playlist_index or '?'}/{job.playlist_count}")
        self.meta_label.setText(" · ".join(meta_bits))

        badge_kind = {
            JobState.QUEUED: "neutral", JobState.DOWNLOADING: "info",
            JobState.POSTPROCESSING: "info", JobState.COMPLETED: "success",
            JobState.CANCELLED: "neutral", JobState.FAILED: "error",
        }[state]
        self.badge.set_kind(badge_kind, STATE_LABEL[state])

        if state is JobState.DOWNLOADING:
            if job.total_bytes:
                self.progress.set_value(job.progress_percent)
                self.progress.set_indeterminate(False)
            else:
                self.progress.set_indeterminate(True)
            speed = utils.human_speed(job.speed)
            eta = utils.human_eta(job.eta)
            self.percent_label.setText(f"{job.progress_percent:.0f}%" if job.total_bytes else "")
            self.meta_label.setText(
                self.meta_label.text() + (f" · {speed}" if speed else "") + (f" · {eta}" if eta else "")
            )
        elif state is JobState.POSTPROCESSING:
            self.progress.set_indeterminate(True)
            self.percent_label.setText("")
        elif state is JobState.COMPLETED:
            self.progress.set_indeterminate(False)
            self.progress.set_value(100.0)
            self.percent_label.setText("100%")
        else:
            self.progress.set_indeterminate(False)
            if state is JobState.FAILED:
                self.progress.set_value(0.0)
            self.percent_label.setText("")

        if state is JobState.FAILED and job.error:
            self.error_label.setText(job.error)
            self.error_label.show()
        else:
            self.error_label.hide()

        known_state = getattr(self, "_last_state", None)
        if known_state != state:
            self._last_state = state
            self._action_buttons()
        if job.thumbnail_url and not getattr(self, "_thumb_loaded", False):
            self._thumb_loaded = True
            cached = self.ctx.thumbnail_loader.cached(job.thumbnail_url)
            if cached:
                self._set_thumb(QPixmap(cached))
            else:
                self.ctx.thumbnail_loader.loaded.connect(self._on_thumb)
                self.ctx.thumbnail_loader.get(job.thumbnail_url)

    def _on_thumb(self, url: str, pixmap) -> None:
        if pixmap is None or url != self.job.thumbnail_url:
            return
        self._set_thumb(QPixmap(pixmap))

    def _set_thumb(self, pm: QPixmap) -> None:
        self.thumb_label.setPixmap(rounded_pixmap(pm, THUMB_W, THUMB_H, 8))


class QueuePage(Page):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(ctx, "Downloads", "", scrollable=False, parent=parent)
        self._cards: dict[str, JobCard] = {}
        self._filter = "all"
        self._visible_order: list[str] = []

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        from anydownloader.ui.widgets import Segmented
        self.filter_segment = Segmented()
        for key, text in (("all", "All"), ("active", "Active"), ("done", "Completed"), ("failed", "Failed")):
            self.filter_segment.addSegment(text, key)
        self.filter_segment.currentChanged.connect(self._set_filter)
        toolbar.addWidget(self.filter_segment)
        toolbar.addStretch(1)

        self.pause_resume_btn = QPushButton("Pause queue")
        self.pause_resume_btn.setObjectName("secondary")
        self.pause_resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pause_resume_btn.setFixedHeight(32)
        self.pause_resume_btn.clicked.connect(self._toggle_pause)
        self.pause_resume_btn.setVisible(False)
        toolbar.addWidget(self.pause_resume_btn)

        clear_btn = QPushButton("Clear finished")
        clear_btn.setObjectName("secondary")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(32)
        clear_btn.clicked.connect(self._clear_finished)
        toolbar.addWidget(clear_btn)
        self.add_body(self._wrap_toolbar(toolbar))

        stats = QHBoxLayout()
        stats.setSpacing(16)
        self.stat_active = label("", "subtitle")
        self.stat_speed = label("", "subtitle")
        stats.addWidget(self.stat_active)
        stats.addWidget(self.stat_speed)
        stats.addStretch(1)
        self.add_body(self._wrap_stats(stats))

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 8, 8)
        self.list_lay.setSpacing(10)
        self.list_lay.addStretch(1)
        self.scroll.setWidget(self.list_host)
        self.add_body(self.scroll, 1)

        self.empty = EmptyState("download", "Nothing here yet",
                                "Paste a link on the Download page and it will appear here.")
        self.list_lay.insertWidget(0, self.empty)
        self.empty.hide()

        m = ctx.manager
        m.job_added.connect(self._on_job_added)
        m.job_updated.connect(lambda job: self._on_job_updated(job))
        m.job_state_changed.connect(self._on_job_updated)
        m.job_removed.connect(self._on_job_removed)
        m.stats_changed.connect(self._on_stats)
        for job in m.jobs:
            self._on_job_added(job)

    def _wrap_toolbar(self, lay) -> QWidget:
        w = QWidget()
        w.setLayout(lay)
        return w

    def _wrap_stats(self, lay) -> QWidget:
        w = QWidget()
        w.setLayout(lay)
        return w

    # -------------------------------------------------------------- plumbing
    def _set_filter(self, key: str) -> None:
        self._filter = key
        for job_id, card_widget in self._cards.items():
            self._apply_visibility(card_widget)

    def _apply_visibility(self, card_widget: JobCard) -> None:
        state = card_widget.job.state
        show = {
            "all": True,
            "active": state.is_active,
            "done": state is JobState.COMPLETED,
            "failed": state is JobState.FAILED,
        }[self._filter]
        card_widget.setVisible(show)

    def _on_job_added(self, job: DownloadJob) -> None:
        if job.job_id in self._cards:
            return
        card = JobCard(job, self.ctx)
        card.actionRequested.connect(self._on_action)
        self._cards[job.job_id] = card
        self.list_lay.insertWidget(1, card)
        self._apply_visibility(card)
        self._refresh_empty()

    def _on_job_updated(self, job: DownloadJob) -> None:
        card = self._cards.get(job.job_id)
        if card is not None:
            card.refresh(job)
            self._apply_visibility(card)

    def _on_job_removed(self, job_id: str) -> None:
        card = self._cards.pop(job_id, None)
        if card is not None:
            card.hide()
            card.deleteLater()
        self._refresh_empty()

    def _on_stats(self, stats: dict) -> None:
        active = stats.get("active", 0)
        queued = stats.get("queued", 0)
        speed = utils.human_speed(stats.get("speed"))
        parts = []
        if active:
            parts.append(f"{active} downloading")
        if queued:
            parts.append(f"{queued} queued")
        if stats.get("paused"):
            parts.append("queue paused")
        self.stat_active.setText(" · ".join(parts) if parts else "Idle")
        self.stat_speed.setText(speed if speed else "")
        active = stats.get("active", 0)
        queued = stats.get("queued", 0)
        if stats.get("paused"):
            self.pause_resume_btn.setText("Resume queue")
            self.pause_resume_btn.setVisible(True)
        elif active == 0 and queued > 0:
            self.pause_resume_btn.setText(f"Start {queued} queued")
            self.pause_resume_btn.setVisible(True)
        elif active > 0:
            self.pause_resume_btn.setText("Pause queue")
            self.pause_resume_btn.setVisible(True)
        else:
            self.pause_resume_btn.setVisible(False)

    def _refresh_empty(self) -> None:
        self.empty.setVisible(not self._cards)

    def _toggle_pause(self) -> None:
        manager = self.ctx.manager
        if manager.queue_paused:
            manager.resume_queue()
            manager.start_all()
            self.ctx.notify("Queue resumed.", "success")
        elif manager.active_count == 0 and manager.queued_count > 0:
            manager.start_all()
        else:
            manager.pause_queue()
            self.ctx.notify("Queue paused — running downloads continue.", "info")

    def _clear_finished(self) -> None:
        removed = self.ctx.manager.clear_finished()
        if removed:
            self.ctx.notify(f"Cleared {removed} finished download{'s' if removed != 1 else ''}.",
                            "info")

    def _on_action(self, job_id: str, action: str) -> None:
        manager = self.ctx.manager
        job = next((j for j in manager.jobs if j.job_id == job_id), None)
        if job is None:
            return
        if action == "cancel":
            manager.cancel(job)
        elif action == "retry" or action == "again":
            manager.retry(job)
            self.ctx.notify("Re-added to the queue.", "success")
        elif action == "remove":
            manager.remove(job)
        elif action == "open" and job.output_path and os.path.isfile(job.output_path):
            os.startfile(job.output_path)  # noqa: S606
        elif action == "locate" and job.output_path:
            _reveal_in_explorer(job.output_path)
        elif action == "copy":
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(job.webpage_url or job.url)
            self.ctx.notify("Link copied to clipboard.", "success")
