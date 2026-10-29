"""Unit tests for pure helpers."""
import pytest

from anydownloader.core import utils


class TestExtractUrls:
    def test_basic(self):
        assert utils.extract_urls("go to https://example.com/a?b=1 now") == [
            "https://example.com/a?b=1"
        ]

    def test_multiple_and_dedupe(self):
        text = "https://a.com/1 http://b.org/2 https://a.com/1"
        assert utils.extract_urls(text) == ["https://a.com/1", "http://b.org/2"]

    def test_trailing_punctuation_stripped(self):
        assert utils.extract_urls("see https://example.com/x.") == ["https://example.com/x"]

    def test_empty(self):
        assert utils.extract_urls("") == []
        assert utils.extract_urls("no links here") == []

    def test_messy_text(self):
        text = ("Check this out!!! https://youtu.be/dQw4w9WgXcQ?si=abc "
                "and also https://vimeo.com/76979871.")
        urls = utils.extract_urls(text)
        assert len(urls) == 2


class TestIsProbableUrl:
    def test_true(self):
        assert utils.is_probable_url("https://example.com")

    def test_false(self):
        assert not utils.is_probable_url("hello world")
        assert not utils.is_probable_url("")
        assert not utils.is_probable_url("ftp://example.com")


class TestHumanFormats:
    def test_size(self):
        assert utils.human_size(None) == "—"
        assert utils.human_size(0) == "—"
        assert utils.human_size(512) == "512 B"
        assert utils.human_size(1536) == "1.5 KB"
        assert utils.human_size(1024 ** 2 * 5.2).startswith("5.2 MB")

    def test_duration(self):
        assert utils.human_duration(None) == "—"
        assert utils.human_duration(59) == "0:59"
        assert utils.human_duration(61) == "1:01"
        assert utils.human_duration(3725) == "1:02:05"

    def test_speed(self):
        assert utils.human_speed(0) == ""
        assert utils.human_speed(1024 * 1024) == "1.0 MB/s"

    def test_eta(self):
        assert utils.human_eta(None) == ""
        assert utils.human_eta(30) == "30s left"
        assert utils.human_eta(125) == "2m 5s left"
        assert utils.human_eta(7200) == "2h 0m left"


class TestParseRateLimit:
    @pytest.mark.parametrize("text,expected", [
        ("", None),
        ("garbage", None),
        ("0", None),
        ("10", 10),
        ("1.5m", int(1.5 * 1024 ** 2)),
        ("2 MB/s", int(2 * 1024 ** 2)),
        ("500k", 500 * 1024),
        ("1g", 1024 ** 3),
    ])
    def test_parsing(self, text, expected):
        assert utils.parse_rate_limit(text) == expected


class TestSafeFilename:
    def test_strips_bad_chars(self):
        assert utils.safe_filename('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"

    def test_length(self):
        assert len(utils.safe_filename("x" * 500)) == 180

    def test_empty(self):
        assert utils.safe_filename("") == "download"


class TestSiteName:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=x", "YouTube"),
        ("https://youtu.be/x", "YouTube"),
        ("https://vimeo.com/1", "Vimeo"),
        ("https://www.tiktok.com/@a/video/1", "TikTok"),
        ("https://example.org/video", "example.org"),
    ])
    def test_names(self, url, expected):
        assert utils.site_name_from_url(url) == expected
