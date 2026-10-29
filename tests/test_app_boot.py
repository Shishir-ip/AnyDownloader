"""Full application boot test — builds every page and exercises interactions."""
import pytest


@pytest.fixture()
def window(qapp, ctx, theme):
    from anydownloader.ui.main_window import MainWindow

    win = MainWindow(ctx)
    win.resize(1080, 700)
    yield win, ctx
    win.close()
    ctx.manager.shutdown(0.5)


class TestBoot:
    def test_window_builds_and_pages_switch(self, window, qapp):
        win, ctx = window
        win.show()
        qapp.processEvents()
        for key in ("download", "queue", "history", "settings", "about"):
            win.switch_page(key)
            qapp.processEvents()

    def test_add_urls_via_page(self, window, qapp):
        win, ctx = window
        win.show()
        qapp.processEvents()
        dl = win.download_page
        dl.url_input.setPlainText("https://youtu.be/abc123 https://vimeo.com/7")
        qapp.processEvents()
        assert dl.current_urls() == ["https://youtu.be/abc123", "https://vimeo.com/7"]
        dl._add(start=False)
        qapp.processEvents()
        assert len(ctx.manager.jobs) == 2
        assert ctx.switch_page is not None

    def test_queue_page_reflects_jobs(self, window, qapp):
        win, ctx = window
        win.show()
        qapp.processEvents()
        from anydownloader.core.models import JobState

        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        qapp.processEvents()
        assert job.job_id in win.queue_page._cards
        card = win.queue_page._cards[job.job_id]
        job.state = JobState.DOWNLOADING
        job.total_bytes = 2000
        job.downloaded_bytes = 500
        job.title = "Test video"
        ctx.manager.job_updated.emit(job)
        qapp.processEvents()
        assert "Downloading" in card.badge._text or card.badge._kind == "info"

    def test_toast_notification(self, window, qapp):
        win, ctx = window
        win.notify("Hello world", "success")
        qapp.processEvents()
        assert any(t._text == "Hello world" for t in win.toast_host._toasts)

    def test_theme_change_restyles(self, window, qapp, theme):
        win, ctx = window
        theme.set_theme("dark")
        qapp.processEvents()
        theme.set_theme("light")
        qapp.processEvents()

    def test_history_page_shows_records(self, window, qapp):
        win, ctx = window
        ctx.history.add({
            "job_id": "h1", "url": "https://a.com/1", "title": "Old video",
            "state": "completed", "site": "YouTube", "profile_label": "1080p",
            "profile_id": "1080p", "created_at": 1.0, "completed_at": 2.0,
        })
        win.switch_page("history")
        qapp.processEvents()
        win.history_page.reload()
        qapp.processEvents()
        assert win.history_page.col.count() > 1

    def test_settings_page_roundtrip(self, window, qapp):
        win, ctx = window
        win.switch_page("settings")
        qapp.processEvents()
        win.settings_page._save("theme", "dark")
        assert ctx.settings.theme == "dark"
        win.settings_page._save("max_concurrent", 5)
        assert ctx.settings.max_concurrent == 5
