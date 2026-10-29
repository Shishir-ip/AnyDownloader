"""Offscreen smoke test: boots the full UI and exercises pages/jobs/toasts."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.argv = ["smoke"]

from PySide6.QtWidgets import QApplication

from anydownloader.core.settings import Settings
from anydownloader.core.history import History
from anydownloader.core.manager import DownloadManager
from anydownloader.ui.theme import ThemeManager
from anydownloader.ui.context import AppContext
from anydownloader.ui.thumbs import ThumbnailLoader
from anydownloader.ui.main_window import MainWindow


def main() -> int:
    settings = Settings.load()
    settings.auto_start = False          # keep the smoke test offline
    settings.save()
    app = QApplication(sys.argv)
    ThemeManager.install(app, settings.theme, settings.accent, settings.reduce_animations)
    history = History()
    manager = DownloadManager(settings, history, title_fetcher=None)
    ctx = AppContext(settings=settings, manager=manager, history=history,
                     thumbnail_loader=ThumbnailLoader())
    win = MainWindow(ctx)
    win.resize(1080, 700)
    win.show()
    app.processEvents()

    for key in ("download", "queue", "history", "settings", "about"):
        win.switch_page(key)
        app.processEvents()
    print("PAGES OK")

    from anydownloader.core.models import DownloadJob, JobState

    job = DownloadJob(url="https://example.com/v1", profile_id="1080p")
    manager.jobs.append(job)
    manager.job_added.emit(job)
    app.processEvents()
    job.state = JobState.DOWNLOADING
    job.total_bytes = 1000
    job.downloaded_bytes = 500
    manager.job_updated.emit(job)
    app.processEvents()
    job.state = JobState.FAILED
    job.error = "test error"
    manager.job_state_changed.emit(job)
    app.processEvents()
    print("QUEUE OK")

    win.notify("hello", "success")
    app.processEvents()
    print("TOAST OK")

    settings.theme = "dark"
    settings.save()
    assert Settings.load().theme == "dark"
    settings.theme = "system"
    settings.save()
    print("SETTINGS OK")

    ThemeManager.instance().set_theme("dark")
    app.processEvents()
    ThemeManager.instance().set_theme("light")
    app.processEvents()
    ThemeManager.instance().set_accent("purple")
    app.processEvents()
    ThemeManager.instance().set_accent("blue")
    print("THEME SWITCH OK")

    # exercise advanced controls on the download page
    dl = win.download_page
    dl.url_input.setPlainText("check https://youtu.be/abc123 and https://vimeo.com/9")
    app.processEvents()
    urls = dl.current_urls()
    assert len(urls) == 2, f"expected 2 urls, got {urls}"
    assert dl.link_count_pill._text == "2 links", dl.link_count_pill._text
    dl._add(start=False)  # adds jobs, switches to queue
    app.processEvents()
    assert len(manager.jobs) >= 3
    print("DOWNLOAD PAGE OK")

    # history page reload with a record
    history.add({"job_id": "x1", "url": "https://youtu.be/abc", "title": "Test video",
                 "state": "completed", "site": "YouTube", "profile_label": "1080p",
                 "created_at": 1700000000.0, "completed_at": 1700000600.0})
    win.switch_page("history")
    app.processEvents()
    print("HISTORY OK")

    win.close()
    app.processEvents()
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
