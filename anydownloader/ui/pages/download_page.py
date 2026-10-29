"""The primary 'New Download' page."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget,
)

from anydownloader.core import engine, tasks, utils
from anydownloader.core.models import PROFILES, profile_by_id
from anydownloader.core.settings import TEMPLATE_VARS_HELP
from anydownloader.ui.context import AppContext
from anydownloader.ui.pages.base import FlowLayout, Page
from anydownloader.ui.pages.preview_dialog import PreviewDialog
from anydownloader.ui.widgets import (
    AnimatedSection, IconButton, PillBadge, QualityCard, Segmented, ToggleSwitch,
    card, key_value_row, label, section_header,
)


class DownloadPage(Page):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(ctx, "Download", "Paste a link — or a whole list of links — to get started.",
                         scrollable=True, parent=parent)
        self._profile_group = QButtonGroup(self)
        self._profile_group.setExclusive(True)
        self._current_kind = "video"
        self._build_url_card()
        self._build_quality_card()
        self._build_destination_card()
        self._build_advanced_section()
        self._build_cta()
        self._sync_quality_cards()

    # ------------------------------------------------------------------ URL
    def _build_url_card(self) -> None:
        frame, lay = card(margins=(14, 12, 14, 14), spacing=10)
        url_card, url_lay = card(margins=(0, 0, 0, 0), spacing=0)
        url_card.setObjectName("cardFlat")
        url_lay.setContentsMargins(0, 0, 0, 0)
        self.url_input = QPlainTextEdit()
        self.url_input.setPlaceholderText(
            "Paste video or playlist links here…\n"
            "One per line — or just drop in messy text, AnyDownloader finds the links."
        )
        self.url_input.setFixedHeight(104)
        self.url_input.setTabChangesFocus(True)
        url_lay.addWidget(self.url_input)

        row = QHBoxLayout()
        row.setSpacing(8)
        paste_btn = QPushButton("Paste from Clipboard")
        paste_btn.setObjectName("secondary")
        paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        paste_btn.setFixedHeight(32)
        paste_btn.clicked.connect(self._paste_clipboard)
        self.clear_btn = IconButton("trash", 15, "Clear")
        self.clear_btn.clicked.connect(lambda: (self.url_input.clear(), self._update_link_count()))
        row.addWidget(paste_btn)
        row.addWidget(self.clear_btn)
        row.addStretch(1)
        self.fetch_btn = QPushButton("Fetch info")
        self.fetch_btn.setObjectName("secondary")
        self.fetch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fetch_btn.setFixedHeight(32)
        self.fetch_btn.clicked.connect(self._fetch_preview)
        row.addWidget(self.fetch_btn)
        self.link_count_pill = PillBadge("0 links", "neutral")
        row.addWidget(self.link_count_pill)

        lay.addWidget(url_card)
        lay.addLayout(row)
        self.url_input.textChanged.connect(self._update_link_count)
        self.add_body(frame)

    def _paste_clipboard(self) -> None:
        from PySide6.QtGui import QClipboard, QGuiApplication
        text = QGuiApplication.clipboard().text()
        urls = utils.extract_urls(text)
        existing = utils.extract_urls(self.url_input.toPlainText())
        merged = existing + [u for u in urls if u not in existing]
        self.url_input.setPlainText("\n".join(merged) if merged else text.strip())
        self._update_link_count()

    def _update_link_count(self) -> None:
        count = len(self.current_urls())
        self.link_count_pill.set_kind("accent" if count else "neutral",
                                      f"{count} link{'s' if count != 1 else ''}")

    def current_urls(self) -> list[str]:
        return utils.extract_urls(self.url_input.toPlainText())

    # -------------------------------------------------------------- quality
    def _build_quality_card(self) -> None:
        frame, lay = card()
        lay.addWidget(section_header("Quality"))
        top = QHBoxLayout()
        top.setSpacing(10)
        self.kind_segment = Segmented()
        self.kind_segment.addSegment("Video", "video")
        self.kind_segment.addSegment("Audio only", "audio")
        top.addWidget(self.kind_segment)
        top.addStretch(1)
        lay.addLayout(top)
        self.profile_flow_host = QWidget()
        self.profile_flow = FlowLayout(spacing=8)
        self.profile_flow_host.setLayout(self.profile_flow)
        lay.addWidget(self.profile_flow_host)
        self.kind_segment.currentChanged.connect(self._sync_quality_cards)
        self.add_body(frame)

    def _sync_quality_cards(self, *_args) -> None:
        kind = self.kind_segment.current()
        self._current_kind = kind
        default_id = self.ctx.settings.default_profile
        if default_id not in {p.id for p in PROFILES if p.kind == kind}:
            default_id = next(p.id for p in PROFILES if p.kind == kind)
        while self.profile_flow.count():
            item = self.profile_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._profile_group = QButtonGroup(self)
        self._profile_group.setExclusive(True)
        for profile in [p for p in PROFILES if p.kind == kind]:
            qc = QualityCard(profile.label, profile.caption)
            qc.setChecked(profile.id == default_id)
            qc.toggled.connect(
                lambda checked, pid=profile.id: self._on_profile_toggled(pid, checked)
            )
            self._profile_group.addButton(qc)
            self.profile_flow.addWidget(qc)
        # preferred card width
        for i in range(self.profile_flow.count()):
            w = self.profile_flow.itemAt(i).widget()
            w.setMinimumWidth(158)
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _on_profile_toggled(self, pid: str, checked: bool) -> None:
        if checked:
            self.ctx.settings.default_profile = pid
            self.ctx.settings.save()

    # ----------------------------------------------------------- destination
    def _build_destination_card(self) -> None:
        frame, lay = card()
        lay.addWidget(section_header("Save to"))
        row = QHBoxLayout()
        row.setSpacing(10)
        folder_glyph_btn = IconButton("folder", 17, "Open folder")
        folder_glyph_btn.clicked.connect(self._open_folder)
        row.addWidget(folder_glyph_btn)
        self.path_label = label(self.ctx.settings.download_dir, "mono")
        self.path_label.setWordWrap(False)
        row.addWidget(self.path_label, 1)
        change_btn = QPushButton("Change…")
        change_btn.setObjectName("secondary")
        change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_btn.setFixedHeight(32)
        change_btn.clicked.connect(self._browse_folder)
        row.addWidget(change_btn)
        lay.addLayout(row)

        organize_row = QHBoxLayout()
        organize_row.setSpacing(8)
        organize_row.addWidget(label("Organize into subfolders"))
        organize_row.addStretch(1)
        self.organize_combo = QComboBox()
        self.organize_combo.addItems(["Never", "By website", "Video / Audio"])
        self.organize_combo.setCurrentIndex(
            {"none": 0, "site": 1, "type": 2}[self.ctx.settings.organize]
        )
        self.organize_combo.setFixedHeight(32)
        self.organize_combo.currentIndexChanged.connect(self._on_organize_changed)
        organize_row.addWidget(self.organize_combo)
        lay.addLayout(organize_row)
        self.add_body(frame)

    def _on_organize_changed(self, index: int) -> None:
        self.ctx.settings.organize = ("none", "site", "type")[index]
        self.ctx.settings.save()

    def _browse_folder(self) -> None:
        start = self.ctx.settings.download_dir or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Choose download folder", start)
        if chosen:
            self.ctx.settings.download_dir = chosen
            self.ctx.settings.save()
            self.path_label.setText(chosen)

    def _open_folder(self) -> None:
        path = self.ctx.settings.download_dir
        if path and os.path.isdir(path):
            os.startfile(path)  # noqa: S606 - Windows shell open

    # -------------------------------------------------------------- advanced
    def _build_advanced_section(self) -> None:
        advanced = QWidget()
        adv_lay = QVBoxLayout(advanced)
        adv_lay.setContentsMargins(0, 0, 0, 0)
        adv_lay.setSpacing(12)

        # --- format
        f_frame, f_lay = card()
        f_lay.addWidget(section_header("Format & filenames"))
        f_lay.addWidget(self._row("film", "Container", "MP4 plays everywhere; MKV keeps everything",
                                  self._container_combo()))
        self.template_edit = QLineEdit(self.ctx.settings.template)
        self.template_edit.setMinimumWidth(240)
        self.template_edit.editingFinished.connect(self._save_template)
        f_lay.addWidget(self._row("file", "Filename template", TEMPLATE_VARS_HELP[:150] + "…",
                                  self.template_edit))
        self.restrict_toggle = ToggleSwitch()
        self.restrict_toggle.setChecked(self.ctx.settings.restrict_names)
        self.restrict_toggle.toggled.connect(self._bind("restrict_names"))
        f_lay.addWidget(self._row("check", "Windows-safe filenames",
                                  "Replace characters Windows dislikes", self.restrict_toggle))
        adv_lay.addWidget(f_frame)

        # --- playlist
        p_frame, p_lay = card()
        p_lay.addWidget(section_header("Playlists"))
        self.playlist_segment = Segmented()
        self.playlist_segment.addSegment("Single video", "single")
        self.playlist_segment.addSegment("Whole playlist", "all")
        self.playlist_segment.addSegment("Range", "range")
        self.playlist_segment.setCurrent(self.ctx.settings.playlist_mode, animate=False)
        self.playlist_segment.currentChanged.connect(self._on_playlist_mode)
        self.playlist_range_edit = QLineEdit(self.ctx.settings.playlist_range)
        self.playlist_range_edit.setPlaceholderText("e.g. 1-5, 8, 11-13")
        self.playlist_range_edit.setFixedWidth(150)
        self.playlist_range_edit.editingFinished.connect(self._save_playlist_range)
        self.playlist_range_edit.setEnabled(self.ctx.settings.playlist_mode == "range")
        p_lay.addWidget(self._row("list", "What to download",
                                  "Applies when a link contains a playlist",
                                  self.playlist_segment))
        p_lay.addWidget(self._row("history", "Playlist items",
                                  "Range of playlist entries to grab", self.playlist_range_edit))
        adv_lay.addWidget(p_frame)

        # --- subtitles
        s_frame, s_lay = card()
        s_lay.addWidget(section_header("Subtitles"))
        self.sub_toggle = ToggleSwitch()
        self.sub_toggle.setChecked(self.ctx.settings.subtitle_enabled)
        self.sub_toggle.toggled.connect(self._bind("subtitle_enabled"))
        s_lay.addWidget(self._row("info", "Download subtitles", "", self.sub_toggle))
        self.sub_langs_edit = QLineEdit(self.ctx.settings.subtitle_langs)
        self.sub_langs_edit.setPlaceholderText("en, de, es")
        self.sub_langs_edit.setFixedWidth(140)
        self.sub_langs_edit.editingFinished.connect(self._save_sub_langs)
        s_lay.addWidget(self._row("globe", "Languages", "Space or comma separated",
                                  self.sub_langs_edit))
        self.sub_auto_toggle = ToggleSwitch()
        self.sub_auto_toggle.setChecked(self.ctx.settings.subtitle_auto)
        self.sub_auto_toggle.toggled.connect(self._bind("subtitle_auto"))
        s_lay.addWidget(self._row("sparkle", "Include auto-generated", "", self.sub_auto_toggle))
        self.sub_embed_toggle = ToggleSwitch()
        self.sub_embed_toggle.setChecked(self.ctx.settings.subtitle_embed)
        self.sub_embed_toggle.toggled.connect(self._bind("subtitle_embed"))
        s_lay.addWidget(self._row("film", "Embed into video", "Soft subtitles, player can toggle",
                                  self.sub_embed_toggle))
        adv_lay.addWidget(s_frame)

        # --- metadata & extras
        m_frame, m_lay = card()
        m_lay.addWidget(section_header("Metadata & extras"))
        self.meta_toggle = ToggleSwitch()
        self.meta_toggle.setChecked(self.ctx.settings.embed_metadata)
        self.meta_toggle.toggled.connect(self._bind("embed_metadata"))
        m_lay.addWidget(self._row("info", "Embed metadata & chapters",
                                  "Title, artist, chapters and more", self.meta_toggle))
        self.thumb_toggle = ToggleSwitch()
        self.thumb_toggle.setChecked(self.ctx.settings.embed_thumbnail)
        self.thumb_toggle.toggled.connect(self._bind("embed_thumbnail"))
        m_lay.addWidget(self._row("image", "Embed thumbnail as cover art", "", self.thumb_toggle))
        self.sponsor_toggle = ToggleSwitch()
        self.sponsor_toggle.setChecked(self.ctx.settings.sponsors_remove)
        self.sponsor_toggle.toggled.connect(self._bind("sponsors_remove"))
        m_lay.addWidget(self._row("zap", "Skip sponsor segments",
                                  "Uses SponsorBlock for supported videos", self.sponsor_toggle))
        self.archive_toggle = ToggleSwitch()
        self.archive_toggle.setChecked(self.ctx.settings.use_archive)
        self.archive_toggle.toggled.connect(self._bind("use_archive"))
        m_lay.addWidget(self._row("check", "Track downloaded items",
                                  "Never download the same video twice", self.archive_toggle))
        adv_lay.addWidget(m_frame)

        # --- network & speed
        n_frame, n_lay = card()
        n_lay.addWidget(section_header("Network & speed"))
        self.limit_edit = QLineEdit(self.ctx.settings.speed_limit)
        self.limit_edit.setPlaceholderText("e.g. 5 MB/s")
        self.limit_edit.setFixedWidth(120)
        self.limit_edit.editingFinished.connect(self._save_limit)
        n_lay.addWidget(self._row("zap", "Speed limit", "Leave empty for full speed",
                                  self.limit_edit))
        self.frags_spin = QSpinBox()
        self.frags_spin.setRange(1, 16)
        self.frags_spin.setValue(self.ctx.settings.concurrent_fragments)
        self.frags_spin.setFixedWidth(80)
        self.frags_spin.valueChanged.connect(self._bind_int("concurrent_fragments"))
        n_lay.addWidget(self._row("film", "Concurrent fragments", "Parallel HLS/DASH piece downloads",
                                  self.frags_spin))
        self.proxy_edit = QLineEdit(self.ctx.settings.proxy)
        self.proxy_edit.setPlaceholderText("http://… or socks5://…")
        self.proxy_edit.setMinimumWidth(200)
        self.proxy_edit.editingFinished.connect(self._save_proxy)
        n_lay.addWidget(self._row("globe", "Proxy", "", self.proxy_edit))
        self.cookies_combo = QComboBox()
        self.cookies_combo.addItem("None", "")
        for browser in ("chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium"):
            self.cookies_combo.addItem(browser.capitalize(), browser)
        idx = self.cookies_combo.findData(self.ctx.settings.cookies_browser)
        self.cookies_combo.setCurrentIndex(max(0, idx))
        self.cookies_combo.currentIndexChanged.connect(self._on_cookies_changed)
        n_lay.addWidget(self._row("clipboard", "Cookies from browser",
                                  "Needed for some private or age-restricted videos",
                                  self.cookies_combo))
        adv_lay.addWidget(n_frame)

        self.advanced_section = AnimatedSection("Advanced options", advanced)
        self.add_body(self.advanced_section)

    def _container_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.addItem("MP4 (recommended)", "mp4")
        combo.addItem("MKV (most compatible)", "mkv")
        combo.addItem("WebM", "webm")
        combo.addItem("Keep original", "original")
        idx = combo.findData(self.ctx.settings.container)
        combo.setCurrentIndex(max(0, idx))
        combo.currentIndexChanged.connect(
            lambda _i, c=combo: self._save_setting("container", c.currentData())
        )
        self._container_combo_ref = combo
        return combo

    def _row(self, icon: str, title: str, caption: str, control: QWidget) -> QWidget:
        return key_value_row(icon, title, caption, control)

    # ---------------------------------------------------------------- binds
    def _bind(self, key: str):
        def _apply(value: bool) -> None:
            self._save_setting(key, value)
        return _apply

    def _bind_int(self, key: str):
        def _apply(value: int) -> None:
            self._save_setting(key, int(value))
        return _apply

    def _save_setting(self, key: str, value) -> None:
        setattr(self.ctx.settings, key, value)
        self.ctx.settings.normalize()
        self.ctx.settings.save()

    def _save_template(self) -> None:
        self._save_setting("template", self.template_edit.text())

    def _save_playlist_range(self) -> None:
        self._save_setting("playlist_range", self.playlist_range_edit.text())

    def _save_sub_langs(self) -> None:
        self._save_setting("subtitle_langs", self.sub_langs_edit.text())

    def _save_limit(self) -> None:
        text = self.limit_edit.text()
        if text and utils.parse_rate_limit(text) is None:
            self.limit_edit.setProperty("error", True)
            self.ctx.notify("That speed limit doesn't look right — try “5 MB/s”.", "error")
            return
        self.limit_edit.setProperty("error", False)
        self._save_setting("speed_limit", text)

    def _save_proxy(self) -> None:
        self._save_setting("proxy", self.proxy_edit.text())

    def _on_cookies_changed(self, index: int) -> None:
        self._save_setting("cookies_browser", self.cookies_combo.itemData(index))

    def _on_playlist_mode(self, mode: str) -> None:
        self.playlist_range_edit.setEnabled(mode == "range")
        self._save_setting("playlist_mode", mode)

    # ------------------------------------------------------------------- CTA
    def _build_cta(self) -> None:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 2, 4, 6)
        lay.setSpacing(12)
        self.summary_label = label("", "subtitle")
        lay.addWidget(self.summary_label, 1)
        add_btn = QPushButton("Add to Queue")
        add_btn.setObjectName("secondary")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedHeight(46)
        add_btn.clicked.connect(lambda: self._add(start=False))
        lay.addWidget(add_btn)
        self.start_btn = QPushButton("Download Now")
        self.start_btn.setObjectName("hero")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setFixedHeight(46)
        self.start_btn.clicked.connect(lambda: self._add(start=True))
        lay.addWidget(self.start_btn)
        self.add_body(bar)

    def _add(self, start: bool) -> None:
        urls = self.current_urls()
        if not urls:
            self.ctx.notify("Paste at least one link first.", "warning")
            return
        profile_id = self.ctx.settings.default_profile
        jobs = self.ctx.manager.add_urls(urls, profile_id)
        if start:
            self.ctx.manager.start_all()
        count = len(jobs)
        self.ctx.notify(
            f"Added {count} download{'s' if count != 1 else ''} · "
            f"{profile_by_id(profile_id).label}",
            "success",
        )
        self.url_input.clear()
        self._update_link_count()
        self.ctx.switch_page("queue")

    # ---------------------------------------------------------------- preview
    def _fetch_preview(self) -> None:
        urls = self.current_urls()
        if not urls:
            self.ctx.notify("Paste a link to preview first.", "warning")
            return
        url = urls[0]
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching…")

        def restore() -> None:
            self.fetch_btn.setEnabled(True)
            self.fetch_btn.setText("Fetch info")

        def on_done(info: dict) -> None:
            restore()
            dlg = PreviewDialog(info, self.ctx, self)
            dlg.exec()

        def on_error(message: str) -> None:
            restore()
            self.ctx.notify(f"Couldn't read this link: {message}", "error")

        settings = self.ctx.settings
        tasks.run_async(
            lambda: engine.probe(url, proxy=settings.proxy,
                                 cookies_browser=settings.cookies_browser,
                                 cookies_file=settings.cookies_file),
            on_done=on_done, on_error=on_error,
        )
