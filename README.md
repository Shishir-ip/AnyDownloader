<p align="center">
  <img src="assets/icon-256.png" width="88" alt="AnyDownloader icon"/>
</p>

<h1 align="center">AnyDownloader</h1>

<p align="center">
  <b>Download video & audio from (almost) anywhere — wrapped in a beautiful, Apple-style desktop app.</b><br/>
  Powered by <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a>. No servers. No accounts. No nonsense.
</p>

<p align="center">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-007AFF?logo=windows11&logoColor=white"/>
  <img alt="tests" src="https://img.shields.io/badge/tests-122%20passing-34C759"/>
  <img alt="license" src="https://img.shields.io/badge/license-MIT-8E8E93"/>
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white"/>
  <img alt="engine" src="https://img.shields.io/badge/engine-yt--dlp-FF3B30"/>
</p>

---

AnyDownloader is a **standalone Windows desktop application** (a single `.exe`) for downloading video and audio from YouTube, Vimeo, TikTok, SoundCloud, Twitter/X, Instagram, Reddit, Dailymotion, Twitch, and **1000+ other sites** via the yt-dlp engine.

It runs **entirely on your machine** — yt-dlp is embedded as a library (not shelled out to a script), FFmpeg ships inside the app, and nothing is ever uploaded or sent to any server.

## ✨ Highlights

| | |
|---|---|
| 🎨 **iOS-inspired UI** | Light & dark themes, 9 accent colours, system-theme following, smooth spring-style animations everywhere |
| 🎯 **Quality presets** | Best available, 4K, 1440p, 1080p, 720p, 480p, 360p — or audio-only: MP3, M4A, Opus, FLAC, WAV |
| 📋 **Single & batch** | Paste one link or a hundred — AnyDownloader extracts every URL from messy text automatically |
| 🔍 **Link preview** | "Fetch info" shows the title, channel, duration, thumbnail and available qualities before you commit |
| 🧠 **Smart queue** | Concurrency control, pause/resume, per-item retry, live speed & ETA, taskbar progress, tray notifications |
| ⚙️ **Advanced options** | Filename templates, subfolder organisation, container choice (MP4/MKV/WebM), subtitles (embed or sidecar), SponsorBlock, download archive, proxy, cookies, speed limits |
| 🗂 **History** | Every finished download remembered, searchable, re-downloadable, CSV-exportable |
| 🔒 **Local-first** | No telemetry. All data in `%LOCALAPPDATA%\AnyDownloader`. |

## 📸 Screenshots

| Download | Queue |
|---|---|
| ![Download page](docs/screenshots/download-light.png) | ![Queue page](docs/screenshots/queue-light.png) |

| Dark mode | History |
|---|---|
| ![Dark mode](docs/screenshots/download-dark.png) | ![History](docs/screenshots/history-light.png) |

## 🚀 Getting started

### Option A — download the exe (recommended)

1. Grab `AnyDownloader.exe` from the [latest release](../../releases/latest).
2. Double-click it. That's it — Python, yt-dlp and FFmpeg are **already inside**.
3. Windows SmartScreen may ask for confirmation on first run (unsigned binary) — click *More info → Run anyway*.

### Option B — run from source

```bash
git clone https://github.com/Shohidul-oss/AnyDownloader.git
cd AnyDownloader
pip install -e .
python -m anydownloader
```

### Option C — build the exe yourself

```bash
pip install -e . pyinstaller
pyinstaller AnyDownloader.spec --noconfirm
# → build/dist/AnyDownloader.exe
```

> **Tip:** run `pytest` to execute the 122-test suite (fully offline).

## 🧭 Using the app

1. **Paste** a link (or many) into the box — or use *Paste from Clipboard*, which pulls every URL out of copied text.
2. **Pick a quality** — video presets or audio-only formats.
3. *(Optional)* expand **Advanced options** for playlists, subtitles, SponsorBlock, proxies, cookies and more.
4. Hit **Download Now** (or *Add to Queue* to batch up) and watch the live progress.

**Keyboard shortcuts:** `Ctrl+1…5` switch pages · `Ctrl+V` paste links · `Ctrl+Enter` start download · `Ctrl+,` settings

## 📁 Where do my files go?

By default: `Downloads\AnyDownloader`. Change it on the Download page or in Settings. With *Organize into subfolders* enabled, files land in per-site (`youtube/…`) or per-type (`Video/…`, `Audio/…`) folders.

## 🛠 Troubleshooting

| Symptom | Fix |
|---|---|
| *"Age-restricted / private"* errors | Enable **Settings → Network → Cookies from browser** (Chrome/Edge/Firefox) or provide a `cookies.txt` |
| *"This website is not supported"* | Update the app — yt-dlp gains extractors weekly; check [releases](../../releases) |
| Slow downloads | Raise *Concurrent fragments* in Advanced options; check your proxy |
| Downloaded file missing | History page → *Show in folder*. If it says "file moved", it was deleted or renamed outside the app |
| Themed title bar wrong | Switch theme to Light/Dark explicitly in Settings |

## 🏗 Project structure

```
anydownloader/
  core/        # engine (yt-dlp wrapper), manager, models, settings, history
  ui/          # theme system, custom widgets, pages, tray, taskbar, icons
assets/        # app icon & branding
docs/          # screenshots
scripts/       # dev tools: smoke test, icon/screenshot generators
tests/         # 122 offline tests (pytest)
.github/       # CI: test + release builds
```

## 🤝 Contributing

Issues and PRs are welcome! Run `pytest` before submitting. Keep the code typed, logged and tested like the surrounding code.

## ⚖️ Legal

AnyDownloader is a UI wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp) and is intended for downloading content you have the right to download (your own uploads, Creative Commons, or where the site permits). Respect copyright and each website's terms of service. The authors are not responsible for misuse.

## 📄 Licence

[MIT](LICENSE) — with bundled components under their own licences: yt-dlp (Unlicense), PySide6/Qt (LGPL-3), FFmpeg binary via imageio-ffmpeg (GPL).
