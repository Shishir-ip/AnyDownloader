"""Shared fixtures: offline settings paths, QApplication, and app context."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _offline_paths(tmp_path, monkeypatch):
    """Redirect every persistence path into a temp dir for isolation."""
    from anydownloader.core import paths

    data_dir = tmp_path / "appdata"
    monkeypatch.setattr(paths, "app_data_dir", lambda: data_dir)
    monkeypatch.setattr(paths, "settings_path", lambda: data_dir / "settings.json")
    monkeypatch.setattr(paths, "history_path", lambda: data_dir / "history.json")
    monkeypatch.setattr(paths, "archive_path", lambda: data_dir / "downloaded.txt")
    monkeypatch.setattr(paths, "default_download_dir", lambda: tmp_path / "Downloads")
    yield data_dir


@pytest.fixture(scope="session")
def qapp():
    """One QApplication for the whole test session (offscreen)."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


@pytest.fixture()
def ctx(qapp, _offline_paths, tmp_path):
    """A wired AppContext with no network access."""
    from anydownloader.core.history import History
    from anydownloader.core.manager import DownloadManager
    from anydownloader.core.settings import Settings
    from anydownloader.ui.context import AppContext
    from anydownloader.ui.thumbs import ThumbnailLoader

    settings = Settings.load()
    settings.auto_start = False
    settings.download_dir = str(tmp_path / "downloads")
    history = History()
    manager = DownloadManager(settings, history, title_fetcher=None)
    return AppContext(settings=settings, manager=manager, history=history,
                      thumbnail_loader=ThumbnailLoader())


@pytest.fixture()
def theme(qapp):
    from anydownloader.ui.theme import ThemeManager

    mgr = ThemeManager.install(qapp, "light", "blue", False)
    yield mgr
