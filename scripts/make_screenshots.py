"""Capture UI screenshots: real platform fonts, but windows never shown on screen."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.argv = ["shots"]

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from anydownloader.core.settings import Settings  # noqa: E402
from anydownloader.core.history import History  # noqa: E402
from anydownloader.core.manager import DownloadManager  # noqa: E402
from anydownloader.ui.theme import ThemeManager  # noqa: E402
from anydownloader.ui.context import AppContext  # noqa: E402
from anydownloader.ui.thumbs import ThumbnailLoader  # noqa: E402
from anydownloader.ui.main_window import MainWindow  # noqa: E402


def main() -> None:
    settings = Settings.load()
    settings.auto_start = False
    settings.clipboard_watch = False
    app = QApplication(sys.argv)
    ThemeManager.install(app, "light", "blue", False)
    history = History()
    manager = DownloadManager(settings, history, title_fetcher=None)
    ctx = AppContext(settings=settings, manager=manager, history=history,
                     thumbnail_loader=ThumbnailLoader())
    win = MainWindow(ctx)
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.resize(1080, 700)
    win.show()
    for _ in range(10):
        app.processEvents()

    # populate the download page with sample text
    win.download_page.url_input.setPlainText(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n"
        "https://vimeo.com/76979871"
    )
    app.processEvents()

    # queue with a few realistic-looking jobs
    from anydownloader.core.models import DownloadJob, JobState
    win.switch_page("queue")
    samples = [
        ("https://youtube.com/watch?v=a1", "Mountain Timelapse in 4K", "YouTube",
         "1080p · Full HD", JobState.DOWNLOADING, 62.0, 2_400_000, 1_540_000),
        ("https://vimeo.com/a2", "Product Launch Aftermovie", "Vimeo",
         "4K · 2160p", JobState.QUEUED, 0.0, None, None),
        ("https://soundcloud.com/a3", "Midnight Drive (Original Mix)", "SoundCloud",
         "MP3", JobState.COMPLETED, 100.0, None, None),
        ("https://tiktok.com/a4", "Street food tour — Tokyo", "TikTok",
         "720p · HD", JobState.FAILED, 0.0, None, None),
    ]
    for url, title, site, profile, state, pct, total, done in samples:
        job = DownloadJob(url=url, profile_id="1080p")
        job.title = title
        job.site = site
        job.state = state
        job.progress_percent = pct
        job.total_bytes = total
        job.downloaded_bytes = done or 0
        job.speed = 2_400_000 if state is JobState.DOWNLOADING else None
        job.eta = 35 if state is JobState.DOWNLOADING else None
        job.error = "This video is private." if state is JobState.FAILED else None
        manager.jobs.append(job)
        manager.job_added.emit(job)
    app.processEvents()

    # history sample rows
    import time
    now = time.time()
    for i, (t, s) in enumerate([("Spring in Kyoto — 8K drone film", "YouTube"),
                                ("Deep Focus — study playlist", "SoundCloud"),
                                ("Unboxing the future", "YouTube")]):
        history.add({"job_id": f"shot{i}", "url": "https://example.com", "title": t,
                     "state": "completed", "site": s, "profile_label": "1080p",
                     "profile_id": "1080p", "created_at": now - i * 86400,
                     "completed_at": now - i * 86400 + 300})

    shots = [
        ("download", "download-light"),
        ("queue", "queue-light"),
        ("history", "history-light"),
        ("settings", "settings-light"),
    ]
    for key, name in shots:
        win.switch_page(key)
        for _ in range(6):
            app.processEvents()
        win.grab().save(str(OUT / f"{name}.png"))

    # dark variants
    ThemeManager.instance().set_theme("dark")
    app.processEvents()
    for key, name in (("download", "download-dark"), ("queue", "queue-dark")):
        win.switch_page(key)
        for _ in range(6):
            app.processEvents()
        win.grab().save(str(OUT / f"{name}.png"))

    win.close()
    manager.shutdown(0.5)
    print("screenshots saved to", OUT)


if __name__ == "__main__":
    main()
