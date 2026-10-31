"""yt-dlp option-building tests (pure, no network)."""
from pathlib import Path

from anydownloader.core import engine
from anydownloader.core.models import DownloadJob, JobOptions, profile_by_id


def make_job(profile_id="1080p", **opt_kwargs) -> DownloadJob:
    return DownloadJob(url="https://example.com/v", profile_id=profile_id,
                       options=JobOptions(download_dir="C:/dl", **opt_kwargs))


class TestFormatSelector:
    def test_best(self):
        assert engine.build_format_selector(profile_by_id("best"), "mp4") == \
            "bestvideo+bestaudio/best"

    def test_height_mp4(self):
        sel = engine.build_format_selector(profile_by_id("720p"), "mp4")
        assert sel.startswith("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]")

    def test_height_mkv(self):
        sel = engine.build_format_selector(profile_by_id("720p"), "mkv")
        assert sel.startswith("bestvideo[height<=720]+bestaudio/")

    def test_audio(self):
        assert engine.build_format_selector(profile_by_id("audio-mp3"), "mp4") == \
            "bestaudio/best"


class TestOutputTemplate:
    def test_plain(self):
        opts = JobOptions(download_dir="C:/dl", organize="none")
        t = engine.output_template(opts, "video")
        assert t.startswith("C:/dl") or t.startswith("C:\\dl")
        assert t.endswith("%(title)s.%(ext)s")

    def test_organize_type(self):
        opts = JobOptions(download_dir="C:/dl", organize="type")
        assert "Audio" in engine.output_template(opts, "audio")
        assert "Video" in engine.output_template(opts, "video")

    def test_organize_site(self):
        opts = JobOptions(download_dir="C:/dl", organize="site")
        assert "%(webpage_url_domain)s" in engine.output_template(opts, "video")

    def test_template_missing_ext(self):
        opts = JobOptions(download_dir="C:/dl", template="%(title)s")
        assert engine.output_template(opts, "video").endswith("%(title)s.%(ext)s")


class TestBuildDownloadOptions:
    def test_base_options(self):
        opts = engine.build_download_options(make_job())
        assert opts["quiet"] is True
        assert opts["retries"] == 10
        assert "ffmpeg_location" in opts  # imageio-ffmpeg present in test env

    def test_audio_job_adds_extract_pp(self):
        job = make_job("audio-mp3")
        opts = engine.build_download_options(job)
        keys = [pp["key"] for pp in opts.get("postprocessors", [])]
        assert "FFmpegExtractAudio" in keys
        assert opts["format"] == "bestaudio/best"

    def test_video_container_merge(self):
        opts = engine.build_download_options(make_job("1080p", container="mkv"))
        assert opts.get("merge_output_format") == "mkv"

    def test_subtitles(self):
        job = make_job("1080p", subtitle_enabled=True, subtitle_langs="en, de",
                       subtitle_embed=True)
        opts = engine.build_download_options(job)
        assert opts["writesubtitles"] is True
        assert opts["subtitleslangs"] == ["en", "de"]
        keys = [pp["key"] for pp in opts.get("postprocessors", [])]
        assert "FFmpegEmbedSubtitle" in keys

    def test_proxy_and_ratelimit(self):
        job = make_job("1080p", proxy="socks5://p:1", speed_limit_bytes=1024,
                       concurrent_fragments=8)
        opts = engine.build_download_options(job)
        assert opts["proxy"] == "socks5://p:1"
        assert opts["ratelimit"] == 1024
        assert opts["concurrent_fragment_downloads"] == 8

    def test_archive(self):
        job = make_job("1080p", use_archive=True)
        opts = engine.build_download_options(job)
        assert "download_archive" in opts

    def test_playlist_modes(self):
        assert engine.build_download_options(make_job())["noplaylist"] is True
        ranged = engine.build_download_options(
            make_job(playlist_mode="range", playlist_range="2-5"))
        assert ranged["playlist_items"] == "2-5"
        assert "noplaylist" not in ranged

    def test_sponsorblock(self):
        job = make_job("1080p", sponsors_remove=True)
        opts = engine.build_download_options(job)
        keys = [pp["key"] for pp in opts.get("postprocessors", [])]
        assert "SponsorBlock" in keys and "ModifyChapters" in keys

    def test_cookies_file_preferred(self, tmp_path):
        cookie = tmp_path / "cookies.txt"
        cookie.write_text("# Netscape", encoding="utf-8")
        job = make_job("1080p", cookies_file=str(cookie), cookies_browser="chrome")
        opts = engine.build_download_options(job)
        assert opts["cookiefile"] == str(cookie)
        assert "cookiesfrombrowser" not in opts

    def test_cookies_browser_fallback(self):
        job = make_job("1080p", cookies_browser="firefox")
        opts = engine.build_download_options(job)
        assert opts["cookiesfrombrowser"] == ("firefox",)


class TestCleanError:
    def test_private_hint(self):
        class E(Exception):
            pass
        assert "private" in engine._clean_error(E("ERROR: [youtube] x: Private video"))

    def test_age_hint(self):
        class E(Exception):
            pass
        msg = engine._clean_error(E("ERROR: Sign in to confirm your age"))
        assert "cookies" in msg

    def test_long_message_truncated(self):
        class E(Exception):
            pass
        assert len(engine._clean_error(E("x" * 1000))) <= 400


class TestFfmpeg:
    def test_ffmpeg_exe_found(self):
        # imageio-ffmpeg is a test dependency, so a binary should resolve
        exe = engine.ffmpeg_exe()
        assert exe and Path(exe).is_file()

    def test_ffmpeg_location_valid(self):
        opts = engine._base_options()
        loc = Path(opts["ffmpeg_location"])
        if engine.media_tools_dir():
            assert (loc / "ffmpeg.exe").is_file() and (loc / "ffprobe.exe").is_file()
        else:
            assert loc.is_file()

    def test_embed_thumbnail_needs_ffprobe(self):
        from anydownloader.core.models import DownloadJob, JobOptions

        job = DownloadJob(url="u", profile_id="1080p",
                          options=JobOptions(download_dir="C:/x", embed_thumbnail=True))
        opts = engine.build_download_options(job)
        keys = [pp["key"] for pp in opts.get("postprocessors", [])]
        assert ("EmbedThumbnail" in keys) == engine.ffprobe_available()
