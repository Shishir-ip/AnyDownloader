"""Prepare the media tools directory (build/media_tools/) for bundling.

Creates:
  build/media_tools/ffmpeg.exe   - copy of the imageio-ffmpeg binary (renamed)
  build/media_tools/ffprobe.exe  - extracted from a static FFmpeg build

yt-dlp postprocessors (embed thumbnail / metadata) need BOTH binaries
reachable in one directory named with their standard names.
"""
from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "build" / "media_tools"

# Static Windows x64 builds (GPL). Primary: BtbN's auto-updating "latest".
# Fallback: gyan.dev release-essentials.
SOURCES = [
    ("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
     lambda name: name.lower().endswith("/bin/ffprobe.exe")),
    ("https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
     "ffmpeg-master-latest-win64-gpl.zip",
     lambda name: name.startswith("ffmpeg") and name.endswith("/bin/ffprobe.exe") or
     (name == "bin/ffprobe.exe")),
]


def ensure_dir() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR


def place_ffmpeg() -> Path:
    """Copy the imageio-ffmpeg binary into media_tools as ffmpeg.exe."""
    import imageio_ffmpeg

    src = Path(imageio_ffmpeg.get_ffmpeg_exe())
    dest = ensure_dir() / "ffmpeg.exe"
    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dest)
    print(f"ffmpeg.exe ready ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def download_ffprobe() -> Path:
    dest = ensure_dir() / "ffprobe.exe"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"ffprobe.exe already present ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    last_error: Exception | None = None
    for url, _matcher in SOURCES:
        try:
            print(f"downloading static FFmpeg build from {url.split('/')[2]} …")
            zip_path = OUT_DIR / "_ffmpeg.zip"
            urllib.request.urlretrieve(url, zip_path)  # noqa: S310 - fixed https URL
            with zipfile.ZipFile(zip_path) as zf:
                member = next(
                    n for n in zf.namelist()
                    if n.lower().endswith("/bin/ffprobe.exe")
                )
                with zf.open(member) as fh, open(dest, "wb") as out:
                    shutil.copyfileobj(fh, out)
            zip_path.unlink(missing_ok=True)
            print(f"ffprobe.exe ready ({dest.stat().st_size / 1e6:.1f} MB)")
            return dest
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last_error = exc
            print(f"  source failed: {exc}")
    raise RuntimeError(f"could not obtain ffprobe: {last_error}")


def main() -> int:
    place_ffmpeg()
    download_ffprobe()
    return 0


if __name__ == "__main__":
    sys.exit(main())
