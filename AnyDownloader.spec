# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AnyDownloader (Windows one-file build).

Build:  pyinstaller AnyDownloader.spec --noconfirm
"""
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for package in ("yt_dlp", "imageio_ffmpeg"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

block_cipher = None

media_tools = Path("build/media_tools")
for _bin in ("ffmpeg.exe", "ffprobe.exe"):
    if (media_tools / _bin).is_file():
        binaries.append((str(media_tools / _bin), "media_tools"))

a = Analysis(
    ["run.py"],
    pathex=[os.path.abspath(".")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "IPython", "jedi"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AnyDownloader",
    icon="assets/app.ico",
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
)
