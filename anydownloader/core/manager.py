"""Queue orchestration: owns jobs, worker threads, retries and stats."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable, Iterable, Optional

from PySide6.QtCore import QObject, Signal

from anydownloader.core import engine, utils
from anydownloader.core.history import History
from anydownloader.core.models import DownloadJob, JobState
from anydownloader.core.settings import Settings

log = logging.getLogger(__name__)

WorkerFactory = Callable[[DownloadJob], Any]


class DownloadManager(QObject):
    """Coordinates all downloads. Lives on the GUI thread."""

    job_added = Signal(object)          # DownloadJob
    job_updated = Signal(object)        # DownloadJob (progress tick)
    job_state_changed = Signal(object)  # DownloadJob (state transition)
    job_removed = Signal(str)           # job_id
    stats_changed = Signal(dict)
    queue_drained = Signal()            # everything reached a terminal state

    def __init__(self, settings: Settings, history: History,
                 worker_factory: WorkerFactory = engine.DownloadWorker,
                 title_fetcher: Optional[Callable[[str], dict]] = None) -> None:
        super().__init__()
        self._settings = settings
        self._history = history
        self._worker_factory = worker_factory
        self._title_fetcher = title_fetcher  # None disables prefetch (tests)
        self.jobs: list[DownloadJob] = []
        self._workers: dict[str, Any] = {}
        self._queue_paused = False
        self._drain_notified = False

        # Background title prefetch (single thread, best effort).
        self._title_queue: queue.Queue = queue.Queue()
        self._title_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ add
    def add_urls(self, urls: Iterable[str], profile_id: str | None = None,
                 options: Any = None) -> list[DownloadJob]:
        profile_id = profile_id or self._settings.default_profile
        opts = options or self._settings.job_options()
        created: list[DownloadJob] = []
        for url in urls:
            url = url.strip()
            if not url:
                continue
            job = DownloadJob(url=url, profile_id=profile_id,
                              site=utils.site_name_from_url(url), options=opts)
            self.jobs.append(job)
            created.append(job)
            self.job_added.emit(job)
        if created:
            self._schedule_title_fetches(created)
            if self._settings.auto_start:
                self.pump()
            self._emit_stats()
        return created

    # --------------------------------------------------------------- workers
    def pump(self) -> None:
        """Start queued jobs while below the concurrency limit."""
        if self._queue_paused:
            return
        max_concurrent = max(1, int(self._settings.max_concurrent))
        for job in list(self.jobs):
            if len(self._workers) >= max_concurrent:
                break
            if job.state is JobState.QUEUED and job.job_id not in self._workers:
                self._start_job(job)
        self._emit_stats()

    def _start_job(self, job: DownloadJob) -> None:
        try:
            worker = self._worker_factory(job)
        except Exception:  # pragma: no cover - defensive
            log.exception("failed to create worker for %s", job.url)
            job.state = JobState.FAILED
            job.error = "Internal error while preparing the download."
            self.job_state_changed.emit(job)
            return
        self._workers[job.job_id] = worker
        worker.updated.connect(self._on_job_updated)
        worker.state_changed.connect(self._on_job_updated)
        worker.finished_job.connect(self._on_job_finished)
        worker.failed.connect(self._on_job_failed)
        worker.cancelled.connect(self._on_job_cancelled)
        worker.finished.connect(lambda jid=job.job_id: self._cleanup_worker(jid))
        job.worker_ref = worker
        worker.start()
        log.info("started job %s (%s)", job.job_id, job.url)

    def _cleanup_worker(self, job_id: str) -> None:
        worker = self._workers.pop(job_id, None)
        if worker is not None:
            worker.deleteLater()
        self._after_terminal_transition()

    # ----------------------------------------------------------- slot wiring
    def _on_job_updated(self, job: DownloadJob) -> None:
        self.job_updated.emit(job)
        self._emit_stats()

    def _on_job_finished(self, job: DownloadJob, info: Any) -> None:
        job.state = JobState.COMPLETED
        job.completed_at = job.completed_at or time.time()
        try:
            self._history.add(job.to_record())
        except Exception:  # pragma: no cover
            log.exception("history write failed")
        self.job_state_changed.emit(job)
        log.info("completed job %s -> %s", job.job_id, job.output_path)

    def _on_job_failed(self, job: DownloadJob, message: str) -> None:
        job.state = JobState.FAILED
        job.error = message
        self.job_state_changed.emit(job)
        log.info("failed job %s: %s", job.job_id, message)

    def _on_job_cancelled(self, job: DownloadJob) -> None:
        job.state = JobState.CANCELLED
        self.job_state_changed.emit(job)

    def _after_terminal_transition(self) -> None:
        self._emit_stats()
        self.pump()
        if self.active_count == 0 and self.queued_count == 0 and self._drain_notified is False:
            self._drain_notified = True
            self.queue_drained.emit()

    # -------------------------------------------------------------- controls
    def cancel(self, job: DownloadJob) -> None:
        if job.state is JobState.QUEUED:
            job.state = JobState.CANCELLED
            job.completed_at = time.time()
            self.job_state_changed.emit(job)
            self._after_terminal_transition()
        else:
            job.cancel_event.set()

    def retry(self, job: DownloadJob) -> None:
        if not job.state.is_terminal:
            return
        job.reset_for_retry()
        self._drain_notified = False
        self.job_state_changed.emit(job)
        self.pump()

    def remove(self, job: DownloadJob) -> None:
        if job.state.is_active:
            self.cancel(job)
        if job.job_id in self._workers:
            return  # will be removed once the worker exits
        try:
            self.jobs.remove(job)
        except ValueError:
            pass
        self.job_removed.emit(job.job_id)
        self._emit_stats()

    def clear_finished(self) -> int:
        removed = 0
        for job in list(self.jobs):
            if job.state.is_terminal and job.job_id not in self._workers:
                self.jobs.remove(job)
                self.job_removed.emit(job.job_id)
                removed += 1
        if removed:
            self._emit_stats()
        return removed

    def start_all(self) -> None:
        self._queue_paused = False
        self._drain_notified = False
        self.pump()

    def pause_queue(self) -> None:
        self._queue_paused = True
        self._emit_stats()

    def resume_queue(self) -> None:
        self._queue_paused = False
        self.pump()

    @property
    def queue_paused(self) -> bool:
        return self._queue_paused

    def set_max_concurrent(self, value: int) -> None:
        self._settings.max_concurrent = utils.clamp(value, 1, 6)
        self.pump()

    # ----------------------------------------------------------------- stats
    @property
    def active_count(self) -> int:
        return sum(1 for j in self.jobs if j.state.is_active)

    @property
    def queued_count(self) -> int:
        return sum(1 for j in self.jobs if j.state is JobState.QUEUED)

    def stats(self) -> dict[str, Any]:
        total_speed = 0.0
        completed = failed = 0
        for job in self.jobs:
            if job.state.is_active and job.speed:
                total_speed += job.speed
            if job.state is JobState.COMPLETED:
                completed += 1
            elif job.state is JobState.FAILED:
                failed += 1
        return {
            "active": self.active_count,
            "queued": self.queued_count,
            "completed": completed,
            "failed": failed,
            "total": len(self.jobs),
            "speed": total_speed,
            "paused": self._queue_paused,
        }

    def _emit_stats(self) -> None:
        self.stats_changed.emit(self.stats())

    # -------------------------------------------------------- title prefetch
    def _schedule_title_fetches(self, jobs: list[DownloadJob]) -> None:
        if self._title_fetcher is None:
            return
        for job in jobs:
            self._title_queue.put(job.job_id)
        if self._title_thread is None or not self._title_thread.is_alive():
            self._title_thread = threading.Thread(
                target=self._title_worker, name="title-prefetch", daemon=True
            )
            self._title_thread.start()

    def _title_worker(self) -> None:
        while True:
            try:
                job_id = self._title_queue.get(timeout=2)
            except queue.Empty:
                return
            job = next((j for j in self.jobs if j.job_id == job_id), None)
            if job is None or job.title or job.state.is_terminal:
                continue
            try:
                info = self._title_fetcher(job.url)  # type: ignore[misc]
            except Exception:
                continue
            if not info:
                continue
            job.title = info.get("title") or job.title
            job.uploader = info.get("uploader") or job.uploader
            job.duration = info.get("duration") or job.duration
            job.thumbnail_url = info.get("thumbnail") or job.thumbnail_url
            job.webpage_url = info.get("webpage_url") or job.webpage_url
            if info.get("n_entries"):
                job.playlist_count = info["n_entries"]
            self.job_updated.emit(job)

    # --------------------------------------------------------------- shutdown
    def shutdown(self, timeout_s: float = 4.0) -> None:
        """Ask active workers to cancel and wait briefly. Workers that do not
        stop in time are deliberately left alive (they die with the process);
        destroying a running QThread would abort the exit."""
        for job in self.jobs:
            if job.state.is_active:
                job.cancel_event.set()
        deadline = time.time() + timeout_s
        for job_id, worker in list(self._workers.items()):
            remaining = max(0.0, deadline - time.time())
            if worker.isRunning() and remaining > 0:
                worker.wait(int(remaining * 1000))
            if worker.isRunning():
                self._workers.pop(job_id, None)  # leak on purpose; see docstring
