"""Persistent download history (JSON store with atomic writes)."""
from __future__ import annotations

import csv
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional

from anydownloader.core import paths

log = logging.getLogger(__name__)

MAX_RECORDS = 2000


class History:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or paths.history_path()
        self._lock = threading.RLock()
        self._records: list[dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------ I/O
    def _load(self) -> None:
        try:
            import json

            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._records = [r for r in data if isinstance(r, dict)]
        except FileNotFoundError:
            self._records = []
        except Exception as exc:
            log.warning("history unreadable, starting fresh: %s", exc)
            self._records = []

    def _save(self) -> None:
        import json

        try:
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self._records[-MAX_RECORDS:], indent=1, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self._path)
        except OSError as exc:  # pragma: no cover
            log.error("could not save history: %s", exc)

    # ------------------------------------------------------------------- API
    def add(self, record: dict[str, Any]) -> None:
        with self._lock:
            self._records.append(record)
            if len(self._records) > MAX_RECORDS * 2:
                self._records = self._records[-MAX_RECORDS:]
            self._save()

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._records))

    def search(self, text: str, kind: str = "all") -> list[dict[str, Any]]:
        text = (text or "").strip().lower()
        out = []
        for rec in self.all():
            if kind != "all":
                rec_kind = "audio" if str(rec.get("profile_id", "")).startswith("audio") else "video"
                if rec_kind != kind:
                    continue
            if text and text not in (
                (rec.get("title") or "") + " " + (rec.get("url") or "") + " " + (rec.get("site") or "")
            ).lower():
                continue
            out.append(rec)
        return out

    def exists_on_disk(self, record: dict[str, Any]) -> bool:
        path = record.get("output_path")
        return bool(path) and Path(path).is_file()

    def delete(self, job_id: str) -> None:
        with self._lock:
            self._records = [r for r in self._records if r.get("job_id") != job_id]
            self._save()

    def clear(self) -> None:
        with self._lock:
            self._records = []
            self._save()

    def export_csv(self, dest: str) -> int:
        rows = self.all()
        if not rows:
            return 0
        columns = ["title", "url", "site", "profile_label", "output_path", "state",
                   "created_at", "completed_at"]
        with open(dest, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(["Title", "URL", "Site", "Quality", "File", "Status",
                             "Added", "Finished"])
            for rec in rows:
                writer.writerow([
                    rec.get("title") or rec.get("url"),
                    rec.get("url", ""),
                    rec.get("site", ""),
                    rec.get("profile_label", ""),
                    rec.get("output_path") or "",
                    rec.get("state", ""),
                    _fmt_ts(rec.get("created_at")),
                    _fmt_ts(rec.get("completed_at")),
                ])
        return len(rows)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._records)
            done = sum(1 for r in self._records if r.get("state") == "completed")
            return {"total": total, "completed": done, "failed": total - done}


def _fmt_ts(ts: Optional[float]) -> str:
    if not ts:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:  # pragma: no cover
        return ""
