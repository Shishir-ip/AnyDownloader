"""The bridge must deliver links on the GUI thread — the v1.0.4 regression.

A plain-Python receiver would get a DIRECT connection (runs on the HTTP
thread); only a QObject-bound slot is queued back to the GUI thread.
"""
import json
import time
import urllib.request

from PySide6.QtCore import QObject, QThread, Slot

from anydownloader.core.bridge import HttpBridge


class _Receiver(QObject):
    """Mirrors the app's _BridgeTarget: a QObject slot on the GUI thread."""

    def __init__(self, app) -> None:
        super().__init__()
        self._app = app
        self.received = []

    @Slot(str, str)
    def accept(self, url: str, profile: str) -> None:
        self.received.append((url, profile, QThread.currentThread() is self._app.thread()))


class _PlainReceiver:
    """What NOT to do — kept to document the failure mode."""

    def __init__(self) -> None:
        self.received = []

    def accept(self, url: str, profile: str) -> None:
        self.received.append((url, profile, False))


def test_links_arrive_on_gui_thread(qapp):
    app = qapp
    receiver = _Receiver(app)
    bridge = HttpBridge(port=0)  # random free port — never touch the real app
    assert bridge.start()
    port = bridge.port
    try:
        bridge.url_received.connect(receiver.accept)

        def post():
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/add",
                data=json.dumps({"url": "https://x.test/v", "profile": "720p"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert json.load(resp)["ok"] is True

        import threading

        t = threading.Thread(target=post)
        t.start()
        t.join(5)

        deadline = time.time() + 3
        while not receiver.received and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)

        assert receiver.received, "link never reached the app"
        url, profile, on_gui_thread = receiver.received[0]
        assert url == "https://x.test/v" and profile == "720p"
        assert on_gui_thread, "slot ran OFF the GUI thread (direct connection bug)"
    finally:
        bridge.stop()
