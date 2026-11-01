"""Localhost bridge: lets the browser extension push links into the queue.

Binds to 127.0.0.1 only. Endpoints:
  GET  /ping          -> {"app","version","ok"}
  POST /add {url}     -> queues the link; {"ok":true}
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from anydownloader import APP_NAME, __version__

log = logging.getLogger(__name__)

DEFAULT_PORT = 7272


class _Handler(BaseHTTPRequestHandler):
    bridge: "HttpBridge" = None  # type: ignore[assignment]

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/ping"):
            self._send(200, {"app": APP_NAME, "version": __version__, "ok": True})
        else:
            self._send(404, {"ok": False, "error": "unknown endpoint"})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/add"):
            self._send(404, {"ok": False, "error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"ok": False, "error": "invalid JSON"})
            return
        url = str(data.get("url") or "").strip()
        if not url:
            self._send(400, {"ok": False, "error": "missing url"})
            return
        profile = str(data.get("profile") or "").strip()
        # Signal.emit is thread-safe; queued to the GUI thread automatically.
        self.bridge.url_received.emit(url, profile)
        self._send(200, {"ok": True})

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default stderr log
        log.debug("bridge: %s", fmt % args)


class HttpBridge(QObject):
    """Tiny localhost HTTP endpoint owned by the GUI app."""

    url_received = Signal(str, str)  # url, profile_id

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        super().__init__()
        self._port = port
        self._server: Optional[ThreadingHTTPServer] = None

    def start(self) -> bool:
        handler = type("BoundHandler", (_Handler,), {"bridge": self})
        try:
            self._server = ThreadingHTTPServer(("127.0.0.1", self._port), handler)
        except OSError as exc:
            log.warning("bridge could not bind port %d: %s", self._port, exc)
            return False
        self._server.daemon_threads = True
        import threading

        threading.Thread(target=self._server.serve_forever, daemon=True,
                         name="anydownloader-bridge").start()
        log.info("bridge listening on http://127.0.0.1:%d", self._port)
        return True

    def stop(self) -> None:
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:  # pragma: no cover
                pass
            self._server = None
