"""Application bootstrap: wiring settings, engine, UI and single-instance guard."""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from anydownloader import APP_NAME, __version__
from anydownloader.core import paths
from anydownloader.core.history import History
from anydownloader.core.manager import DownloadManager
from anydownloader.core.settings import Settings
from anydownloader.ui import appicon, taskbar_win
from anydownloader.ui.context import AppContext
from anydownloader.ui.main_window import MainWindow
from anydownloader.ui.theme import ThemeManager
from anydownloader.ui.thumbs import ThumbnailLoader

log = logging.getLogger(__name__)


def _accept_bridge_url(window: "MainWindow", url: str, profile_id: str = "") -> None:
    """Queue a link arriving from the browser extension and start it now."""
    from anydownloader.core.models import PROFILES

    if profile_id not in {prof.id for prof in PROFILES}:
        profile_id = ""
    if any(j.url == url and not j.state.is_terminal for j in window.ctx.manager.jobs):
        window.notify("Already in the queue.", "info")
        return
    window.ctx.manager.add_urls([url], profile_id or None)
    window.ctx.manager.start_all()  # an explicit user action always starts
    window.notify("Sent from browser: " + url[:60], "success")
    window.switch_page("queue")


def urls_from_args(args: list) -> list:
    """Extract plain URLs and anydownloader://add?url=... links from argv."""
    from urllib.parse import parse_qs, urlparse

    urls: list = []
    for raw in args[1:]:
        raw = raw.strip()
        if raw.startswith("anydownloader://"):
            parsed = urlparse(raw)
            host_or_path = (parsed.netloc + parsed.path).strip("/").lower()
            if host_or_path == "add":
                for value in parse_qs(parsed.query).get("url", []):
                    value = value.strip()
                    if value.startswith(("http://", "https://")) and value not in urls:
                        urls.append(value)
        elif raw.startswith(("http://", "https://")) and raw not in urls:
            urls.append(raw)
    return urls


def _forward_to_running_instance(urls: list, port: int) -> None:
    """Secondary instance: hand our URLs to the running app's bridge."""
    import urllib.request

    for url in urls:
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/add",
                data=json.dumps({"url": url}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass


def _single_instance_guard() -> bool:
    """Best-effort single instance via a named mutex on Windows."""
    if sys.platform != "win32":
        return True
    import ctypes

    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "AnyDownloader_SingleInstance")
    return not (handle and ctypes.windll.kernel32.GetLastError() == 183)  # ERROR_ALREADY_EXISTS


def main() -> int:
    paths.setup_logging()
    if not _single_instance_guard():
        cli_urls = urls_from_args(sys.argv)
        if cli_urls:
            _forward_to_running_instance(cli_urls, settings.bridge_port)
        print("AnyDownloader is already running.", file=sys.stderr)
        return 0

    settings = Settings.load()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("AnyDownloader")
    app.setWindowIcon(appicon.icon())

    theme = ThemeManager.install(app, settings.theme, settings.accent,
                                 settings.reduce_animations)
    theme.theme_changed.connect(
        lambda: taskbar_win.apply_titlebar_theme(
            0, theme.resolve() == "dark"  # re-applied per-window below
        )
    )

    history = History()
    from anydownloader.core import engine
    manager = DownloadManager(settings, history, title_fetcher=engine.fetch_title)
    ctx = AppContext(settings=settings, manager=manager, history=history,
                     thumbnail_loader=ThumbnailLoader())
    window = MainWindow(ctx)
    window.show()

    cli_urls = urls_from_args(sys.argv)
    if cli_urls:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(
            300, lambda: (ctx.manager.add_urls(cli_urls), ctx.manager.start_all())
        )
        log.info("queued %d link(s) from command line", len(cli_urls))

    if settings.bridge_enabled:
        from anydownloader.core.bridge import HttpBridge

        bridge = HttpBridge(settings.bridge_port)
        if bridge.start():
            bridge.url_received.connect(_accept_bridge_url)
        ctx.bridge = bridge

    # CI/launch verification: exit cleanly shortly after the window is up.
    if os.environ.get("ANYDOWNLOADER_AUTOTEST") == "1":
        from PySide6.QtCore import QTimer

        from anydownloader.core import engine
        from anydownloader.core.models import DownloadJob, JobOptions

        # Frozen-mode self-check: option building touches the bundled
        # ffmpeg/ffprobe paths, which dev runs exercise differently.
        probe_job = DownloadJob(url="https://example.com/x", profile_id="1080p",
                                options=JobOptions(download_dir="C:/x",
                                                   embed_thumbnail=True))
        options = engine.build_download_options(probe_job)
        assert engine.ffprobe_available(), "ffprobe missing in bundle"
        assert Path(options["ffmpeg_location"]).is_dir()
        log.info("frozen self-check OK: %s", options["ffmpeg_location"])

        QTimer.singleShot(1500, app.quit)
        result = app.exec()
        window.close()
        return result
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
