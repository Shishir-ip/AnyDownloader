"""Settings page: appearance, downloads, behaviour, network and advanced."""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from anydownloader import __version__
from anydownloader.core import engine, paths, tasks, updates, utils
from anydownloader.core.settings import TEMPLATE_VARS_HELP
from anydownloader.ui.context import AppContext
from anydownloader.ui.pages.base import Page
from anydownloader.ui.theme import ACCENTS, ThemeManager
from anydownloader.ui.widgets import (
    IconGlyph, Segmented, ToggleSwitch, card, key_value_row, label, section_header,
)


class AccentRow(QWidget):
    changed = Signal(str)

    def __init__(self, current: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current = current
        self.setFixedHeight(36)
        self._dots = list(ACCENTS.keys())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N801
        x = event.position().x()
        width = self.width()
        step = width / len(self._dots)
        index = int(x // step)
        if 0 <= index < len(self._dots):
            self._current = self._dots[index]
            self.changed.emit(self._current)
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N801
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        step = self.width() / len(self._dots)
        d = 22.0
        for i, key in enumerate(self._dots):
            cx = step * i + step / 2 - d / 2
            cy = (self.height() - d) / 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(ACCENTS[key]))
            painter.drawEllipse(QRectF(cx, cy, d, d))
            if key == self._current:
                painter.setPen(QPen(QColor("#FFFFFF"), 2.4))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(cx + 3, cy + 3, d - 6, d - 6))


class SettingsPage(Page):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(ctx, "Settings", "", scrollable=True, parent=parent)
        s = ctx.settings
        self._updating = False

        # ------------------------------------------------------ appearance
        a_frame, a_lay = card()
        a_lay.addWidget(section_header("Appearance"))
        theme_seg = Segmented()
        theme_seg.addSegment("Light", "light")
        theme_seg.addSegment("Dark", "dark")
        theme_seg.addSegment("System", "system")
        theme_seg.setCurrent(s.theme, animate=False)
        theme_seg.currentChanged.connect(lambda v: self._save("theme", v))
        a_lay.addWidget(key_value_row("sun", "Theme", "Follow system matches Windows",
                                      theme_seg))
        self.accent_row = AccentRow(s.accent)
        self.accent_row.changed.connect(lambda v: self._save("accent", v))
        a_lay.addWidget(key_value_row("sparkle", "Accent colour", "", self.accent_row))
        reduce_toggle = ToggleSwitch()
        reduce_toggle.setChecked(s.reduce_animations)
        reduce_toggle.toggled.connect(lambda v: self._save("reduce_animations", v))
        a_lay.addWidget(key_value_row("zap", "Reduce animations",
                                      "Turn off transitions for maximum performance",
                                      reduce_toggle))
        self.add_body(a_frame)

        # ------------------------------------------------------ downloads
        d_frame, d_lay = card()
        d_lay.addWidget(section_header("Downloads"))
        self.dir_label = label(s.download_dir, "mono")
        change = QPushButton("Change…")
        change.setObjectName("secondary")
        change.setCursor(Qt.CursorShape.PointingHandCursor)
        change.clicked.connect(self._browse_dir)
        dir_row = QWidget()
        rl = QHBoxLayout(dir_row)
        rl.setContentsMargins(14, 10, 14, 10)
        rl.setSpacing(12)
        rl.addWidget(IconGlyph("folder", 20, "accent"))
        col = QVBoxLayout()
        col.addWidget(label("Save location"))
        col.addWidget(self.dir_label)
        rl.addLayout(col, 1)
        rl.addWidget(change)
        d_lay.addWidget(dir_row)

        organize = QComboBox()
        organize.addItem("Never", "none")
        organize.addItem("By website", "site")
        organize.addItem("Video / Audio", "type")
        organize.setCurrentIndex(("none", "site", "type").index(s.organize))
        organize.currentIndexChanged.connect(
            lambda _i, c=organize: self._save("organize", c.currentData()))
        d_lay.addWidget(key_value_row("folder", "Subfolder organisation", "", organize))

        quality = QComboBox()
        from anydownloader.core.models import PROFILES
        for p in PROFILES:
            quality.addItem(f"{p.label} — {p.caption}", p.id)
        idx = quality.findData(s.default_profile)
        quality.setCurrentIndex(max(0, idx))
        quality.currentIndexChanged.connect(
            lambda _i, c=quality: self._save("default_profile", c.currentData()))
        d_lay.addWidget(key_value_row("film", "Default quality", "", quality))

        template = QLineEdit(s.template)
        template.setMinimumWidth(240)
        template.editingFinished.connect(lambda: self._save("template", template.text()))
        d_lay.addWidget(key_value_row("file", "Filename template", TEMPLATE_VARS_HELP[:150] + "…",
                                      template))
        safe = ToggleSwitch()
        safe.setChecked(s.restrict_names)
        safe.toggled.connect(lambda v: self._save("restrict_names", v))
        d_lay.addWidget(key_value_row("check", "Windows-safe filenames", "", safe))
        self.add_body(d_frame)

        # ------------------------------------------------------ behaviour
        b_frame, b_lay = card()
        b_lay.addWidget(section_header("Behaviour"))
        auto = ToggleSwitch()
        auto.setChecked(s.auto_start)
        auto.toggled.connect(lambda v: self._save("auto_start", v))
        b_lay.addWidget(key_value_row("zap", "Start downloads automatically",
                                      "Otherwise new items wait in the queue", auto))

        self.concurrent_slider = QSlider(Qt.Orientation.Horizontal)
        self.concurrent_slider.setRange(1, 6)
        self.concurrent_slider.setValue(s.max_concurrent)
        self.concurrent_slider.setFixedWidth(180)
        self.concurrent_value = label(str(s.max_concurrent), "bigNumber")
        self.concurrent_slider.valueChanged.connect(
            lambda v: (self.concurrent_value.setText(str(v)),
                       self._save("max_concurrent", v)))
        slider_row = QWidget()
        sl = QHBoxLayout(slider_row)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)
        sl.addWidget(self.concurrent_slider)
        sl.addWidget(self.concurrent_value)
        b_lay.addWidget(key_value_row("list", "Downloads at the same time",
                                      "More is not always faster", slider_row))

        clips = ToggleSwitch()
        clips.setChecked(s.clipboard_watch)
        clips.toggled.connect(lambda v: self._save("clipboard_watch", v))
        b_lay.addWidget(key_value_row("clipboard", "Watch clipboard for links",
                                      "Offers to download a link when you copy one", clips))
        bridge_toggle = ToggleSwitch()
        bridge_toggle.setChecked(s.bridge_enabled)
        bridge_toggle.toggled.connect(lambda v: self._save("bridge_enabled", v))
        b_lay.addWidget(key_value_row("link", "Browser extension bridge",
                                      "Lets the companion extension send links to the app",
                                      bridge_toggle))
        notif = ToggleSwitch()
        notif.setChecked(s.notifications)
        notif.toggled.connect(lambda v: self._save("notifications", v))
        b_lay.addWidget(key_value_row("bell", "Notifications",
                                      "Toast + system notification when downloads finish", notif))
        tray = ToggleSwitch()
        tray.setChecked(s.minimize_to_tray)
        tray.toggled.connect(lambda v: self._save("minimize_to_tray", v))
        b_lay.addWidget(key_value_row("moon", "Close to tray",
                                      "Keep the app running in the background", tray))
        self.add_body(b_frame)

        # ------------------------------------------------------ network
        n_frame, n_lay = card()
        n_lay.addWidget(section_header("Network"))
        limit = QLineEdit(s.speed_limit)
        limit.setPlaceholderText("e.g. 5 MB/s — empty for full speed")
        limit.setFixedWidth(150)
        limit.editingFinished.connect(lambda: self._save("speed_limit", limit.text()))
        n_lay.addWidget(key_value_row("zap", "Speed limit", "", limit))

        proxy = QLineEdit(s.proxy)
        proxy.setPlaceholderText("http://host:port or socks5://host:port")
        proxy.setMinimumWidth(220)
        proxy.editingFinished.connect(lambda: self._save("proxy", proxy.text()))
        n_lay.addWidget(key_value_row("globe", "Proxy", "", proxy))

        cookies = QComboBox()
        cookies.addItem("None", "")
        for browser in ("chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium"):
            cookies.addItem(browser.capitalize(), browser)
        cidx = cookies.findData(s.cookies_browser)
        cookies.setCurrentIndex(max(0, cidx))
        cookies.currentIndexChanged.connect(
            lambda _i, c=cookies: self._save("cookies_browser", c.currentData()))
        n_lay.addWidget(key_value_row("clipboard", "Cookies from browser",
                                      "For private / age-restricted videos", cookies))

        cookie_file_btn = QPushButton("Choose cookies.txt…" if s.cookies_file else "Optional cookies.txt file")
        cookie_file_btn.setObjectName("secondary")
        cookie_file_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cookie_file_btn.clicked.connect(self._pick_cookie_file)
        self.cookie_file_btn = cookie_file_btn
        n_lay.addWidget(key_value_row("file", "Cookies file",
                                      "Exported cookies.txt overrides browser cookies",
                                      cookie_file_btn))
        self.add_body(n_frame)

        # ------------------------------------------------------ advanced
        v_frame, v_lay = card()
        v_lay.addWidget(section_header("Advanced"))
        archive = ToggleSwitch()
        archive.setChecked(s.use_archive)
        archive.toggled.connect(lambda v: self._save("use_archive", v))
        v_lay.addWidget(key_value_row("check", "Download archive",
                                      "Skips anything downloaded before", archive))

        self.ytdlp_label = label(f"yt-dlp {engine.ytdlp_version()}", "subtitle")
        open_data = QPushButton("Open data folder")
        open_data.setObjectName("secondary")
        open_data.setCursor(Qt.CursorShape.PointingHandCursor)
        open_data.clicked.connect(lambda: os.startfile(str(paths.app_data_dir())))  # noqa: S606
        v_lay.addWidget(key_value_row("info", "Data & logs",
                                      str(paths.app_data_dir()), open_data))
        v_lay.addWidget(key_value_row("external", "Engine version", "",
                                      self.ytdlp_label))

        self.update_status = label("", "subtitle")
        check_updates = QPushButton("Check for updates")
        check_updates.setObjectName("secondary")
        check_updates.setCursor(Qt.CursorShape.PointingHandCursor)
        check_updates.clicked.connect(self._check_updates)
        v_lay.addWidget(key_value_row("retry", "Application updates",
                                      f"AnyDownloader {__version__}", check_updates))
        v_lay.addWidget(self.update_status)

        reset = QPushButton("Reset all settings")
        reset.setObjectName("danger")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.clicked.connect(self._reset)
        v_lay.addWidget(key_value_row("trash", "Reset", "Restore every setting to default",
                                      reset))
        self.add_body(v_frame)

    # ---------------------------------------------------------------- actions
    def _save(self, key: str, value) -> None:
        if self._updating:
            return
        s = self.ctx.settings
        setattr(s, key, value)
        s.normalize()
        s.save()
        mgr = ThemeManager.instance()
        if key == "theme":
            mgr.set_theme(s.theme)
        elif key == "accent":
            mgr.set_accent(s.accent)
        elif key == "reduce_animations":
            mgr.set_reduce_animations(s.reduce_animations)
        elif key == "max_concurrent":
            self.ctx.manager.set_max_concurrent(int(s.max_concurrent))

    def _browse_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose download folder",
                                                  self.ctx.settings.download_dir)
        if chosen:
            self._save("download_dir", chosen)
            self.dir_label.setText(chosen)

    def _pick_cookie_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose cookies.txt", "",
                                              "cookies.txt (*.txt);;All files (*.*)")
        if path:
            self._save("cookies_file", path)
            self.cookie_file_btn.setText("Using " + os.path.basename(path))

    def _check_updates(self) -> None:
        self.update_status.setText("Checking…")

        def done(info: dict) -> None:
            if info.get("update_available"):
                self.update_status.setText(
                    f"Version {info.get('latest')} is available!")
                self.ctx.notify(
                    f"AnyDownloader {info.get('latest')} is available.",
                    "info", action_text="Open download page",
                    on_action=lambda: __import__("webbrowser").open(info.get("url", "")),
                )
            else:
                self.update_status.setText("You are up to date.")

        def failed(message: str) -> None:
            self.update_status.setText("Could not check for updates.")

        tasks.run_async(updates.check_latest, on_done=done, on_error=failed)

    def _reset(self) -> None:
        from anydownloader.core.settings import Settings
        defaults = Settings()
        s = self.ctx.settings
        self._updating = True
        for field in ("theme", "accent", "reduce_animations", "organize", "container",
                      "template", "restrict_names", "default_profile", "max_concurrent",
                      "speed_limit", "auto_start", "clipboard_watch", "notifications",
                      "minimize_to_tray", "subtitle_enabled", "subtitle_langs",
                      "subtitle_auto", "subtitle_embed", "embed_metadata", "embed_thumbnail",
                      "sponsors_remove", "playlist_mode", "playlist_range", "proxy",
                      "cookies_browser", "cookies_file", "use_archive"):
            setattr(s, field, getattr(defaults, field))
        s.normalize()
        s.save()
        self._updating = False
        mgr = ThemeManager.instance()
        mgr.set_theme(s.theme)
        mgr.set_accent(s.accent)
        self.ctx.notify("Settings restored to defaults. Restart to refresh the page.",
                        "success")
