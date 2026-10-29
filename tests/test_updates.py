"""Update checker helpers (no network)."""
import pytest

from anydownloader.core.updates import _semver_gt, _parse


class TestSemver:
    @pytest.mark.parametrize("a,b,expected", [
        ("1.0.1", "1.0.0", True),
        ("1.1.0", "1.0.9", True),
        ("2.0.0", "2.0.0", False),
        ("1.0.0", "1.0.1", False),
        ("", "1.0.0", False),
        ("banana", "1.0.0", False),
        ("v1.2.3", "1.2.2", True),
    ])
    def test_compare(self, a, b, expected):
        assert _semver_gt(a, b) is expected

    def test_parse(self):
        assert _parse("1.2.3") == (1, 2, 3)
        assert _parse("v1.2.3-rc1") == (1, 2, 3)
        assert _parse("oops") is None
