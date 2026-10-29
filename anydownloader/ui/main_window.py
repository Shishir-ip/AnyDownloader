"""Main application window: sidebar navigation + page stack + system integration."""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QMenu, QStackedWidget,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from anydownloader import APP_NAME, APP_TAGLINE, __version__
from anydownloader.core import utils
from anydownloader.core.manager import DownloadManager
from anydownloader.ui import appicon, icons
from anydownloader.ui.context import AppContext
from anydownloader.ui.pages.about_page import AboutPage
from anydownloader.ui.pages.download_page import DownloadPage
from anydownloader.ui.pages.history_page import HistoryPage
from anydownloader.ui.pages.queue_page import QueuePage
from anydownloader.ui.pages.settings_page import SettingsPage
from anydownloader.ui.taskbar_win import TaskbarProgress, apply_titlebar_theme
from anydownloader.ui.theme import ThemeManager, current_palette
from anydownloader.ui.widgets import FadeSlideStack, NavButton, ToastHost, label

PAGES = [
    ("download", "Download", "download"),
    ("queue", "Downloads", "list"),
    ("history", "History", "history"),
    ("settings", "Settings", "gear"),
    ("about", "About", "info"),
]


class MainWindow(QMainWindow):
    clipboard_link_spotted = Signal(str)

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.ctx.window = self
        self.setWindowTitle(f"{APP_NAME}  ·  v{__version__}")
        self.setWindowIcon(appicon.icon())
        self.resize(1080, 700)
        self.setMinimumSize(900, 620)

        self._taskbar = TaskbarProgress()
        self._last_taskbar = -1
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setInterval(900)
        self._clipboard_timer.timeout.connect(self._poll_clipboard)
        self._last_clipboard = ""

        self._build_ui()
        self._build_tray()
        self._shortcuts()
        self._restore_geometry()
        self._apply_frameless_theme()

        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        self.ctx.manager.stats_changed.connect(self._on_stats)
        self.ctx.manager.job_state_changed.connect(self._on_job_state)
        self.ctx.manager.queue_drained.connect(self._on_queue_drained)

        if self.ctx.settings.clipboard_watch:
            self._clipboard_timer.start()
        if self.ctx.settings.check_updates_on_start:
            QTimer.singleShot(4000, self._background_update_check)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # --- sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(216)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(14, 20, 14, 16)
        sb.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(appicon.badge_pixmap(38))
        logo.setFixedSize(38, 38)
        brand.addWidget(logo)
        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand_col.addWidget(label(APP_NAME, "title"))
        tag = label("v" + __version__, "caption")
        brand_col.addWidget(tag)
        brand.addLayout(brand_col)
        brand.addStretch(1)
        sb.addLayout(brand)
        sb.addSpacing(18)

        self._nav_buttons: dict[str, NavButton] = {}
        for key, text, icon_name in PAGES:
            btn = NavButton(icon_name, text)
            btn.clicked.connect(lambda _=False, k=key: self.switch_page(k))
            self._nav_buttons[key] = btn
            sb.addWidget(btn)
        sb.addStretch(1)

        self.nav_status = label("", "caption")
        self.nav_status.setWordWrap(True)
        sb.addWidget(self.nav_status)
        root.addWidget(sidebar)

        # --- pages
        self.stack = FadeSlideStack()
        self.ctx.switch_page = self.switch_page
        self.download_page = DownloadPage(self.ctx)
        self.queue_page = QueuePage(self.ctx)
        self.history_page = HistoryPage(self.ctx)
        self.settings_page = SettingsPage(self.ctx)
        self.about_page = AboutPage(self.ctx)
        for page in (self.download_page, self.queue_page, self.history_page,
                     self.settings_page, self.about_page):
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        self.toast_host = ToastHost(self)
        self.ctx.notify = self.notify

        self.switch_page("download", animate=False)

    # ---------------------------------------------------------------- pages
    def switch_page(self, key: str, animate: bool = True) -> None:
        index = {k: i for i, (k, _t, _ic) in enumerate(PAGES)}.get(key, 0)
        for name, btn in self._nav_buttons.items():
            btn.setChecked(name == key)
        if animate:
            self.stack.setCurrentIndex(index)
        else:
            self.stack.setCurrentIndex(index)  # FadeSlideStack handles animation
        self._update_nav_status()

    def _update_nav_status(self) -> None:
        stats = self.ctx.manager.stats()
        bits = []
        if stats.get("active"):
            bits.append(f"{stats['active']} downloading")
        if stats.get("queued"):
            bits.append(f"{stats['queued']} queued")
        if stats.get("paused"):
            bits.append("paused")
        self.nav_status.setText(" · ".join(bits) if bits else "Ready")

    # ---------------------------------------------------------------- toast
    def notify(self, text: str, kind: str = "info", action_text: str = "",
               on_action=None, duration_ms: int = 4000) -> None:
        self.toast_host.show_toast(text, kind, action_text, on_action, duration_ms)

    def resizeEvent(self, event) -> None:  # noqa: N801
        super().resizeEvent(event)
        self.toast_host.resize(self.size())
        self.toast_host._relayout()

    # ---------------------------------------------------------------- tray
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(appicon.icon(), self)
        menu = QMenu()
        show_action = QAction("Open AnyDownloader", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)
        menu.addSeparator()
        self.tray_pause = QAction("Pause queue", self)
        self.tray_pause.triggered.connect(self._tray_toggle_pause)
        menu.addAction(self.tray_pause)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._really_quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        if self.ctx.settings.minimize_to_tray:
            self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _tray_toggle_pause(self) -> None:
        if self.ctx.manager.queue_paused:
            self.ctx.manager.resume_queue()
        else:
            self.ctx.manager.pause_queue()
        self._sync_tray_text()

    def _sync_tray_text(self) -> None:
        self.tray_pause.setText("Resume queue" if self.ctx.manager.queue_paused else "Pause queue")

    # ------------------------------------------------------------ shortcuts
    def _shortcuts(self) -> None:
        for i, (key, _t, _ic) in enumerate(PAGES, start=1):
            sc = QShortcut(QKeySequence(f"Ctrl+{i}"), self)
            sc.activated.connect(lambda k=key: self.switch_page(k))
        settings_sc = QShortcut(QKeySequence("Ctrl+,"), self)
        settings_sc.activated.connect(lambda: self.switch_page("settings"))
        paste_sc = QShortcut(QKeySequence.Paste, self)
        paste_sc.activated.connect(self._paste_into_download)

    def _paste_into_download(self) -> None:
        if self.stack.currentIndex() != 0:
            self.switch_page("download")
        self.download_page.url_input.setFocus()
        self.download_page._paste_clipboard()

    def keyPressEvent(self, event) -> None:  # noqa: N801
        if event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if self.stack.currentIndex() == 0:
                self.download_page._add(start=True)
                return
        super().keyPressEvent(event)

    # ------------------------------------------------------------- clipboard
    def _poll_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text or text == self._last_clipboard:
            return
        self._last_clipboard = text
        urls = utils.extract_urls(text)
        if not urls:
            return
        self.clipboard_link_spotted.emit(urls[0])
        if not self.ctx.settings.clipboard_watch:
            return
        if any(j.url == urls[0] and not j.state.is_terminal for j in self.ctx.manager.jobs):
            return
        self.notify("Link detected in clipboard.", "info",
                    action_text="Use it", on_action=lambda: self._paste_into_download())

    # ------------------------------------------------------------- progress
    def _on_stats(self, stats: dict) -> None:
        self._update_nav_status()
        self._sync_tray_text()
        active = stats.get("active", 0)
        hwnd = int(self.winId())
        if active:
            self._taskbar.set_state(hwnd, 1)
        elif self._last_taskbar not in (0, -1):
            self._taskbar.clear(hwnd)
            self._last_taskbar = 0

    def _on_job_state(self, job) -> None:
        hwnd = int(self.winId())
        if job.state.value == "downloading" and job.total_bytes:
            self._taskbar.set_progress(hwnd, int(job.downloaded_bytes), int(job.total_bytes))
            self._last_taskbar = 1
        elif job.state.is_terminal:
            if not any(j.state.is_active for j in self.ctx.manager.jobs):
                self._taskbar.clear(hwnd)
                self._last_taskbar = 0

    def _on_queue_drained(self) -> None:
        stats = self.ctx.manager.stats()
        failed = stats.get("failed", 0)
        completed = stats.get("completed", 0)
        if completed or failed:
            text = f"All done — {completed} downloaded" + (f", {failed} failed" if failed else "")
            self.notify(text, "error" if failed and not completed else "success")
            if self.ctx.settings.notifications and self.tray.isVisible() and not self.isVisible():
                self.tray.showMessage(APP_NAME, text,
                                      QSystemTrayIcon.MessageIcon.Information, 3500)

    # ---------------------------------------------------------------- theme
    def _apply_frameless_theme(self) -> None:
        apply_titlebar_theme(int(self.winId()),
                             ThemeManager.instance().resolve() == "dark")

    def _on_theme_changed(self) -> None:
        self._apply_frameless_theme()

    def _background_update_check(self) -> None:
        from anydownloader.core import tasks, updates

        def done(info: dict) -> None:
            if info.get("update_available"):
                self.notify(
                    f"AnyDownloader {info.get('latest')} is available.",
                    "info", action_text="See release",
                    on_action=lambda: __import__("webbrowser").open(info.get("url", "")),
                    duration_ms=8000,
                )

        tasks.run_async(updates.check_latest, on_done=done, on_error=None)

    # ------------------------------------------------------------- geometry
    def _restore_geometry(self) -> None:
        geo = self.ctx.settings.window_geometry
        if geo:
            try:
                parts = [int(p) for p in geo.split(",")]
                if len(parts) == 4:
                    self.setGeometry(*parts)
            except ValueError:
                pass

    def _save_geometry(self) -> None:
        g = self.geometry()
        self.ctx.settings.window_geometry = f"{g.x()},{g.y()},{g.width()},{g.height()}"
        self.ctx.settings.save()

    # ------------------------------------------------------------- shutdown
    def closeEvent(self, event) -> None:  # noqa: N801
        if self.ctx.settings.minimize_to_tray and self.tray.isVisible():
            event.ignore()
            self.hide()
            self.notify("AnyDownloader keeps running in the tray. Quit from the tray menu.",
                        "info", duration_ms=3000)
            return
        self._save_geometry()
        self.ctx.manager.shutdown()
        event.accept()

    def _really_quit(self) -> None:
        self.ctx.settings.minimize_to_tray = False
        self._save_geometry()
        self.ctx.manager.shutdown()
        QApplication.quit()
