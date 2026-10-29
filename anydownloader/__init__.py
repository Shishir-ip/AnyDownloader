"""AnyDownloader — a polished, Apple-style video & audio downloader for Windows.

Powered by yt-dlp (embedded as a library — no server, no external tools).
"""
from __future__ import annotations

APP_NAME = "AnyDownloader"
APP_ID = "io.github.anydownloader.app"
APP_TAGLINE = "Download video & audio from (almost) anywhere"
ORG_NAME = "AnyDownloader"

# Bump on release. CI tags this version when publishing.
__version__ = "1.0.0"

# GitHub repository used for update checks (owner set at publish time).
GITHUB_OWNER = "Shohidul-oss"  # overridden by CI via -D flag when building
GITHUB_REPO = "AnyDownloader"
