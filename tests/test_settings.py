"""Settings persistence and validation tests."""
from anydownloader.core.settings import Settings, VALID_THEMES


class TestSettingsRoundtrip:
    def test_save_load(self):
        s = Settings.load()
        s.theme = "dark"
        s.accent = "purple"
        s.max_concurrent = 4
        s.save()
        s2 = Settings.load()
        assert s2.theme == "dark"
        assert s2.accent == "purple"
        assert s2.max_concurrent == 4

    def test_corrupt_file_falls_back(self, _offline_paths):
        _offline_paths.mkdir(parents=True, exist_ok=True)
        (_offline_paths / "settings.json").write_text("{not json", encoding="utf-8")
        s = Settings.load()
        assert s.theme in VALID_THEMES


class TestNormalize:
    def test_bad_theme(self):
        s = Settings(theme="midnight")
        s.normalize()
        assert s.theme == "system"

    def test_concurrency_clamped(self):
        s = Settings(max_concurrent=99)
        s.normalize()
        assert s.max_concurrent == 6
        s.max_concurrent = -3
        s.normalize()
        assert s.max_concurrent == 1

    def test_bad_speed_limit_cleared(self):
        s = Settings(speed_limit="fast")
        s.normalize()
        assert s.speed_limit == ""

    def test_good_speed_limit_kept(self):
        s = Settings(speed_limit="5 MB/s")
        s.normalize()
        assert s.speed_limit == "5 MB/s"
        assert s.speed_limit_bytes == 5 * 1024 ** 2

    def test_default_download_dir_filled(self):
        s = Settings(download_dir="")
        s.normalize()
        assert s.download_dir

    def test_subtitle_langs_cleaned(self):
        s = Settings(subtitle_langs="en,, de ,")
        s.normalize()
        assert s.subtitle_langs == "en de"

    def test_bad_playlist_mode(self):
        s = Settings(playlist_mode="everything")
        s.normalize()
        assert s.playlist_mode == "single"


class TestJobOptionsSnapshot:
    def test_snapshot_inherits_settings(self):
        s = Settings.load()
        s.proxy = "http://proxy:1"
        s.speed_limit = "1m"
        s.subtitle_enabled = True
        opts = s.job_options()
        assert opts.proxy == "http://proxy:1"
        assert opts.speed_limit_bytes == 1024 ** 2
        assert opts.subtitle_enabled is True
