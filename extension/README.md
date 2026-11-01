# AnyDownloader Companion (browser extension)

Sends videos from any page straight into the AnyDownloader desktop app.

## Install (Chrome / Edge / Brave)

1. Make sure the AnyDownloader desktop app is **running** (bridge enabled in Settings → Behaviour).
2. Open your browser's extensions page:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. Enable **Developer mode** (toggle, top corner).
4. Click **Load unpacked** and select this `extension` folder
   (installed apps: `C:\Program Files\AnyDownloader\browser-extension`).

## Use

- Click the AnyDownloader icon on any page → **Send this page** queues it in the app.
- On pages with direct media files (mp4/mp3/…), they are listed with individual **Download** buttons.

The extension talks to the app over a localhost-only bridge (`http://127.0.0.1:7272`).
Nothing leaves your machine.
