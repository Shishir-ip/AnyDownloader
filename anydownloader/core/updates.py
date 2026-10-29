"""Check GitHub Releases for a newer AnyDownloader version."""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Any, Optional

from anydownloader import GITHUB_OWNER, GITHUB_REPO, __version__

log = logging.getLogger(__name__)

_TIMEOUT = 12


def _fetch_latest() -> Optional[dict[str, Any]]:
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "AnyDownloader"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def check_latest() -> dict[str, Any]:
    """Returns {'current':…, 'latest':…, 'update_available': bool, 'url':…} or raises."""
    data = _fetch_latest() or {}
    latest = (data.get("tag_name") or "").lstrip("vV")
    html_url = data.get("html_url") or f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    return {
        "current": __version__,
        "latest": latest,
        "update_available": _semver_gt(latest, __version__),
        "url": html_url,
        "notes": data.get("body") or "",
    }


def _semver_gt(a: str, b: str) -> bool:
    pa = _parse(a)
    pb = _parse(b)
    if pa is None or pb is None:
        return False
    return pa > pb


def _parse(v: str) -> Optional[tuple[int, ...]]:
    m = re.match(r"^[vV]?(\d+)\.(\d+)\.(\d+)", v.strip())
    if not m:
        return None
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]
