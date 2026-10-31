"""Application bootstrap: wiring settings, engine, UI and single-instance guard."""
from __future__ import annotations

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
