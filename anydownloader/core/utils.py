"""Small pure helpers shared across the app."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]{}]+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    """Pull every http(s) URL out of arbitrary pasted text, de-duplicated, order kept."""
    if not text:
        return []
    seen: set[str] = set()
    urls: list[str] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:!?")
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def is_probable_url(text: str) -> bool:
    stripped = text.strip()
    if not stripped or " " in stripped:
        return False
    try:
        p = urlparse(stripped)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def human_size(num: float | None) -> str:
    if not num or num <= 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} PB"


def human_duration(seconds: float | None) -> str:
    if not seconds or seconds < 0:
        return "—"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def human_speed(bytes_per_sec: float | None) -> str:
    if not bytes_per_sec or bytes_per_sec <= 0:
        return ""
    return f"{human_size(bytes_per_sec)}/s"


def human_eta(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds > 24 * 3600:
        return ""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s left"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m left"
    return f"{m}m {s}s left"


_SPEED_UNITS = {
    "": 1, "b": 1,
    "k": 1024, "kb": 1024, "kib": 1024,
    "m": 1024 ** 2, "mb": 1024 ** 2, "mib": 1024 ** 2,
    "g": 1024 ** 3, "gb": 1024 ** 3, "gib": 1024 ** 3,
}

_SPEED_RE = re.compile(r"^\s*([\d.]+)\s*([a-z/]*)\s*$", re.IGNORECASE)


def parse_rate_limit(text: str) -> int | None:
    """Parse human input like ``10``, ``1.5m``, ``2 MB/s`` into bytes/sec."""
    if not text or not text.strip():
        return None
    m = _SPEED_RE.match(text.strip().lower().replace("/s", "").replace("/sec", ""))
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).rstrip("/")
    mult = _SPEED_UNITS.get(unit)
    if mult is None:
        return None
    rate = int(value * mult)
    return rate if rate > 0 else None


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def safe_filename(name: str, max_length: int = 180) -> str:
    """Make a string safe as a Windows filename component."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return (cleaned[:max_length] or "download")


def site_name_from_url(url: str) -> str:
    """Pretty site label: 'youtube.com', 'vimeo', …"""
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    host = host.removeprefix("www.").removeprefix("m.")
    base = host.split(".")[-2] if host.count(".") >= 1 else host
    if not base:
        return host
    special = {
        "youtube": "YouTube", "youtu": "YouTube", "vimeo": "Vimeo",
        "tiktok": "TikTok", "twitch": "Twitch", "x": "X", "twitter": "X (Twitter)",
        "soundcloud": "SoundCloud", "dailymotion": "Dailymotion",
        "facebook": "Facebook", "instagram": "Instagram", "reddit": "Reddit",
        "bilibili": "Bilibili",
    }
    return special.get(base, host or base)
