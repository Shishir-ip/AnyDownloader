"""Write the v1.0.0 release payload to build/_release.json."""
import json

body = {
    "tag_name": "v1.0.0",
    "target_commitish": "main",
    "name": "AnyDownloader v1.0.0",
    "body": (
        "**First public release of AnyDownloader.**\n\n"
        "A polished, Apple-style video & audio downloader for Windows, powered by yt-dlp.\n\n"
        "## Highlights\n"
        "- Single-file `AnyDownloader.exe` — Python, yt-dlp and FFmpeg are all inside\n"
        "- Light / dark / system themes with 9 accent colours and smooth animations\n"
        "- Single & batch downloads: paste messy text, AnyDownloader finds every link\n"
        "- Quality presets: Best / 4K / 1440p / 1080p / 720p / 480p / 360p\n"
        "- Audio-only: MP3, M4A, Opus, FLAC, WAV\n"
        "- Smart queue: concurrency control, pause/resume, retry, live speed & ETA\n"
        "- Advanced options: playlists, subtitles, SponsorBlock, download archive,\n"
        "  proxy, cookies, speed limits, filename templates\n"
        "- Searchable history with CSV export\n"
        "- Link preview before download\n\n"
        "## Install\n"
        "1. Download `AnyDownloader-v1.0.0-windows-x64.exe` below\n"
        "2. Double-click and run (SmartScreen: *More info → Run anyway*)\n\n"
        "> Requires Windows 10/11 (64-bit). No other dependencies.\n"
    ),
    "draft": False,
    "prerelease": False,
}
with open("build/_release.json", "w", encoding="utf-8") as fh:
    json.dump(body, fh, ensure_ascii=False)
print("payload written")
