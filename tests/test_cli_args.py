"""Command-line / protocol URL parsing."""
from anydownloader.app import urls_from_args


class TestUrlsFromArgs:
    def test_plain_urls(self):
        args = ["app", "https://a.com/1", "noise", "http://b.org/2"]
        assert urls_from_args(args) == ["https://a.com/1", "http://b.org/2"]

    def test_protocol_link(self):
        args = ["app", "anydownloader://add?url=" + "https%3A%2F%2Fx.test%2Fv%3Fid%3D7"]
        assert urls_from_args(args) == ["https://x.test/v?id=7"]

    def test_protocol_with_profile(self):
        args = ["app",
                "anydownloader://add?url=https%3A%2F%2Fx.test%2Fa&profile=720p"]
        assert urls_from_args(args) == ["https://x.test/a"]

    def test_dedupe_and_ignore_non_urls(self):
        args = ["app", "https://a.com/1", "https://a.com/1", "--flag", "file.txt"]
        assert urls_from_args(args) == ["https://a.com/1"]

    def test_empty(self):
        assert urls_from_args(["app"]) == []
