"""Model behaviour tests."""
import threading

from anydownloader.core.models import (
    JobOptions, JobState, PROFILES, DownloadJob, profile_by_id,
)


class TestProfiles:
    def test_registry_has_video_and_audio(self):
        kinds = {p.kind for p in PROFILES}
        assert kinds == {"video", "audio"}

    def test_lookup(self):
        assert profile_by_id("1080p").height == 1080
        assert profile_by_id("audio-mp3").audio_codec == "mp3"
        assert profile_by_id("nope").id == "best"  # falls back


class TestJobState:
    def test_terminality(self):
        assert JobState.COMPLETED.is_terminal
        assert JobState.FAILED.is_terminal
        assert JobState.CANCELLED.is_terminal
        assert not JobState.DOWNLOADING.is_terminal
        assert JobState.DOWNLOADING.is_active
        assert not JobState.QUEUED.is_active


class TestJobOptions:
    def test_roundtrip(self):
        opts = JobOptions(download_dir="C:/x", container="mkv", subtitle_langs="en de")
        data = opts.to_dict()
        restored = JobOptions.from_dict(data)
        assert restored == opts

    def test_from_dict_ignores_unknown_keys(self):
        restored = JobOptions.from_dict({"download_dir": "a", "bogus": 1})
        assert restored.download_dir == "a"


class TestDownloadJob:
    def test_defaults(self):
        job = DownloadJob(url="https://example.com")
        assert job.state is JobState.QUEUED
        assert len(job.job_id) == 12
        assert job.cancel_event is not None

    def test_display_title_prefers_entry(self):
        job = DownloadJob(url="https://example.com", title="Main")
        assert job.display_title == "Main"
        job.entry_title = "Entry 3"
        assert job.display_title == "Entry 3"

    def test_record_roundtrip(self):
        job = DownloadJob(url="https://example.com", profile_id="audio-mp3",
                          title="Song", site="Web")
        job.state = JobState.COMPLETED
        job.output_path = "C:/x/Song.mp3"
        rec = job.to_record()
        restored = DownloadJob.from_record(rec)
        assert restored.url == job.url
        assert restored.profile_id == "audio-mp3"
        assert restored.state is JobState.COMPLETED
        assert restored.output_path == "C:/x/Song.mp3"
        assert restored.job_id == job.job_id

    def test_from_record_bad_state(self):
        job = DownloadJob.from_record({"url": "u", "state": "weird"})
        assert job.state is JobState.COMPLETED

    def test_reset_for_retry(self):
        job = DownloadJob(url="u")
        job.state = JobState.FAILED
        job.error = "boom"
        old_event = job.cancel_event
        job.reset_for_retry()
        assert job.state is JobState.QUEUED
        assert job.error is None
        assert job.cancel_event is not old_event
        assert not job.cancel_event.is_set()

    def test_cancel_event_threading(self):
        job = DownloadJob(url="u")
        assert isinstance(job.cancel_event, threading.Event)
