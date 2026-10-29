"""Run blocking callables on a QThreadPool and deliver results on the GUI thread."""
from __future__ import annotations

import logging
import traceback
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

log = logging.getLogger(__name__)


class _TaskSignals(QObject):
    done = Signal(object)
    error = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], on_done: Callable[[Any], None] | None,
                 on_error: Callable[[str], None] | None) -> None:
        super().__init__()
        self.signals = _TaskSignals()
        if on_done:
            self.signals.done.connect(on_done)
        if on_error:
            self.signals.error.connect(on_error)

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn()  # type: ignore[attr-defined]
        except Exception:
            message = traceback.format_exc(limit=3)
            log.debug("async task failed:\n%s", message)
            self._safe_emit(self.signals.error, message.strip().splitlines()[-1])
        else:
            self._safe_emit(self.signals.done, result)

    @staticmethod
    def _safe_emit(signal, value) -> None:
        """Deliver a result unless the receiving object died (app shutting down)."""
        try:
            signal.emit(value)
        except RuntimeError:
            log.debug("signal receiver gone; result dropped")


def run_async(fn: Callable[[], Any],
              on_done: Callable[[Any], None] | None = None,
              on_error: Callable[[str], None] | None = None) -> None:
    """Execute ``fn()`` on a worker thread; callbacks run on the calling thread."""
    task = _Task(fn, on_done, on_error)
    task.fn = fn  # type: ignore[attr-defined]
    QThreadPool.globalInstance().start(task)
