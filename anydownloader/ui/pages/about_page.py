"""About page: credits, licences, shortcuts."""
from __future__ import annotations

import webbrowser
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from anydownloader import APP_TAGLINE, GITHUB_OWNER, GITHUB_REPO, __version__
from anydownloader.core import engine
from anydownloader.ui.context import AppContext
from anydownloader.ui.pages.base import Page
from anydownloader.ui.widgets import card, label, section_header

SHORTCUTS = [
    ("Ctrl + 1…5", "Jump between pages"),
    ("Ctrl + Enter", "Add links and start downloading"),
    ("Ctrl + V", "Paste links into the box"),
    ("Ctrl + ,", "Open settings"),
    ("Esc", "Dismiss dialogs"),
]

CREDITS = [
    ("yt-dlp", "The download engine — supports 1000+ websites", "https://github.com/yt-dlp/yt-dlp"),
    ("PySide6 / Qt", "The GUI framework", "https://www.qt.io"),
    ("FFmpeg (imageio-ffmpeg)", "Merging, transcoding and metadata", "https://ffmpeg.org"),
    ("Feather Icons", "UI icon inspiration (MIT)", "https://feathericons.com"),
]


class AboutPage(Page):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None) -> None:
        super().__init__(ctx, "About", "", scrollable=True, parent=parent)

        hero = QWidget()
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(0, 8, 0, 8)
        hero_lay.setSpacing(4)
        from anydownloader.ui.widgets import IconGlyph
        glyph = IconGlyph("download", 44, "accent")
        hero_lay.addWidget(glyph, 0, Qt.AlignmentFlag.AlignHCenter)
        name = label(f"AnyDownloader {__version__}", "title")
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hero_lay.addWidget(name)
        tagline = label(APP_TAGLINE, "subtitle")
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hero_lay.addWidget(tagline)
        engine_label = label(f"Powered by yt-dlp {engine.ytdlp_version()} · FFmpeg bundled",
                             "caption")
        engine_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hero_lay.addWidget(engine_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        github = QPushButton("Star on GitHub")
        github.setObjectName("primary")
        github.setCursor(Qt.CursorShape.PointingHandCursor)
        github.clicked.connect(
            lambda: webbrowser.open(f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"))
        buttons.addWidget(github)
        issues = QPushButton("Report an issue")
        issues.setObjectName("secondary")
        issues.setCursor(Qt.CursorShape.PointingHandCursor)
        issues.clicked.connect(
            lambda: webbrowser.open(f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues"))
        buttons.addWidget(issues)
        buttons.addStretch(1)
        hero_lay.addLayout(buttons)
        self.add_body(hero)

        sc_frame, sc_lay = card()
        sc_lay.addWidget(section_header("Keyboard shortcuts"))
        for keys, description in SHORTCUTS:
            row = QHBoxLayout()
            key_label = label(keys, "mono")
            key_label.setFixedWidth(130)
            row.addWidget(key_label)
            row.addWidget(label(description), 1)
            sc_lay.addLayout(row)
        self.add_body(sc_frame)

        cr_frame, cr_lay = card()
        cr_lay.addWidget(section_header("Built with"))
        for title, description, url in CREDITS:
            row = QHBoxLayout()
            t = label(title)
            t.setFixedWidth(200)
            row.addWidget(t)
            row.addWidget(label(description), 1)
            link = QPushButton("Open")
            link.setObjectName("secondary")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.setFixedHeight(28)
            link.clicked.connect(lambda _=False, u=url: webbrowser.open(u))
            row.addWidget(link)
            cr_lay.addLayout(row)
        lic = label(
            "AnyDownloader is MIT-licensed. It bundles yt-dlp (Unlicense), a PySide6 runtime "
            "(LGPL-3) and an FFmpeg binary (GPL, via imageio-ffmpeg). "
            "Please respect creators' rights and the terms of the websites you download from.",
            "caption")
        lic.setWordWrap(True)
        cr_lay.addWidget(lic)
        self.add_body(cr_frame)
