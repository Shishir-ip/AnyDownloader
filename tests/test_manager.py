"""DownloadManager tests using a scripted fake worker (no network, no threads)."""
import pytest
from PySide6.QtCore import QObject, Signal

from anydownloader.core.models import DownloadJob, JobState, JobOptions


class FakeWorker(QObject):
    updated = Signal(object)
    state_changed = Signal(object)
    finished_job = Signal(object, object)
    failed = Signal(object, str)
    cancelled = Signal(object)
    finished = Signal()

    instances = []

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.started = False
        self.is_running = False
        FakeWorker.instances.append(self)

    def start(self):
        self.started = True
        self.is_running = True
        self.job.state = JobState.DOWNLOADING
        self.state_changed.emit(self.job)

    def isRunning(self):
        return self.is_running

    def wait(self, ms=0):
        self.is_running = False
        return True

    def deleteLater(self):
        pass

    # scripted helpers used by tests
    def finish_ok(self, path="C:/dl/file.mp4"):
        self.job.state = JobState.COMPLETED
        self.job.output_path = path
        self.job.completed_at = 1.0
        self.finished_job.emit(self.job, {})
        self.is_running = False
        self.finished.emit()

    def fail(self, message="boom"):
        self.job.state = JobState.FAILED
        self.job.error = message
        self.job.completed_at = 1.0
        self.failed.emit(self.job, message)
        self.is_running = False
        self.finished.emit()

    def cancel(self):
        self.job.state = JobState.CANCELLED
        self.cancelled.emit(self.job)
        self.is_running = False
        self.finished.emit()


@pytest.fixture()
def fake_env(qapp, ctx, monkeypatch):
    FakeWorker.instances = []
    created = []

    def factory(job):
        w = FakeWorker(job)
        created.append(w)
        return w

    ctx.manager._worker_factory = factory
    return ctx, created


class TestAddUrls:
    def test_add_creates_jobs(self, fake_env):
        ctx, _ = fake_env
        jobs = ctx.manager.add_urls(["https://a.com/1", "https://a.com/2"])
        assert len(jobs) == 2
        assert len(ctx.manager.jobs) == 2
        assert jobs[0].state is JobState.QUEUED
        assert jobs[0].options.download_dir == ctx.settings.download_dir

    def test_add_skips_blank(self, fake_env):
        ctx, _ = fake_env
        jobs = ctx.manager.add_urls(["", "  ", "https://a.com/1"])
        assert len(jobs) == 1

    def test_no_autostart(self, fake_env):
        ctx, created = fake_env
        ctx.settings.auto_start = False
        ctx.manager.add_urls(["https://a.com/1"])
        assert created == []


class TestConcurrency:
    def test_limit_respected(self, fake_env):
        ctx, created = fake_env
        ctx.settings.max_concurrent = 2
        ctx.manager.add_urls(["https://a.com/1", "https://a.com/2", "https://a.com/3"])
        ctx.manager.start_all()
        assert len(created) == 2
        assert ctx.manager.queued_count == 1
        # finishing one starts the next
        created[0].finish_ok()
        assert len(created) == 3

    def test_pause_blocks_pump(self, fake_env):
        ctx, created = fake_env
        ctx.manager.pause_queue()
        ctx.manager.add_urls(["https://a.com/1"])
        ctx.manager.pump()
        assert created == []
        ctx.manager.resume_queue()
        assert len(created) == 1


class TestLifecycle:
    def test_success_flow(self, fake_env):
        ctx, created = fake_env
        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        ctx.manager.start_all()
        created[0].finish_ok(path="C:/dl/video.mp4")
        assert job.state is JobState.COMPLETED
        assert job.output_path == "C:/dl/video.mp4"
        assert ctx.history.all()[0]["state"] == "completed"

    def test_failure_flow(self, fake_env):
        ctx, created = fake_env
        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        ctx.manager.start_all()
        created[0].fail("site down")
        assert job.state is JobState.FAILED
        assert job.error == "site down"

    def test_cancel_queued(self, fake_env):
        ctx, created = fake_env
        ctx.settings.max_concurrent = 1
        jobs = ctx.manager.add_urls(["https://a.com/1", "https://a.com/2"])
        ctx.manager.start_all()
        ctx.manager.cancel(jobs[1])
        assert jobs[1].state is JobState.CANCELLED

    def test_retry_terminal(self, fake_env):
        ctx, created = fake_env
        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        ctx.manager.start_all()
        created[0].fail("x")
        ctx.manager.retry(job)
        # a worker slot is free, so the job restarts immediately
        assert job.state in (JobState.QUEUED, JobState.DOWNLOADING)
        assert job.error is None
        assert len(created) == 2

    def test_retry_active_is_noop(self, fake_env):
        ctx, created = fake_env
        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        ctx.manager.start_all()
        ctx.manager.retry(job)
        assert job.state is JobState.DOWNLOADING

    def test_remove_finished(self, fake_env):
        ctx, created = fake_env
        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        ctx.manager.start_all()
        created[0].finish_ok()
        ctx.manager.remove(job)
        assert job not in ctx.manager.jobs

    def test_clear_finished(self, fake_env):
        ctx, created = fake_env
        ctx.settings.max_concurrent = 1
        jobs = ctx.manager.add_urls(["https://a.com/1", "https://a.com/2"])
        ctx.manager.start_all()
        created[0].finish_ok()
        # second job still queued; only one removable
        removed = ctx.manager.clear_finished()
        assert removed == 1

    def test_stats(self, fake_env):
        ctx, created = fake_env
        ctx.settings.max_concurrent = 1
        ctx.manager.add_urls(["https://a.com/1", "https://a.com/2"])
        stats = ctx.manager.stats()
        assert stats["queued"] == 2
        assert stats["total"] == 2
        ctx.manager.start_all()
        stats = ctx.manager.stats()
        assert stats["active"] == 1
        assert stats["queued"] == 1


class TestDrainSignal:
    def test_drained_emitted_once(self, fake_env, qapp):
        ctx, created = fake_env
        fired = []
        ctx.manager.queue_drained.connect(lambda: fired.append(1))
        job = ctx.manager.add_urls(["https://a.com/1"])[0]
        ctx.manager.start_all()
        created[0].finish_ok()
        assert fired == [1]


class TestShutdown:
    def test_shutdown_waits(self, fake_env):
        ctx, created = fake_env
        ctx.manager.add_urls(["https://a.com/1"])
        ctx.manager.start_all()
        ctx.manager.shutdown(0.1)
        assert created[0].job.cancel_event.is_set()
