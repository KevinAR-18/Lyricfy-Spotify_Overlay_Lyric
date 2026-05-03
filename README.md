# Lyricfy

Lyricfy is a lightweight Windows lyric overlay for Spotify built with Python and PySide6. It reads the current track from Spotify, syncs lyrics using local `.lrc` files or LRCLIB, and shows them in a compact always-on-top overlay.

## Features

- Reads the currently playing track from Spotify
- Displays synced lyrics using Spotify playback progress
- Checks local `.lrc` files first, then falls back to LRCLIB
- Retries lyric lookup automatically when a new track does not resolve on the first attempt
- Compact frameless overlay that stays on top
- Draggable overlay with snap-back behavior near the last saved position
- System tray controls for show, hide, settings, and exit
- In-app settings for Spotify credentials, redirect URI, lyric offset, and colors
- Auto-created `.env` file on first launch
- Separate Spotify token cache for packaged builds
- Automatic `.lrc` cache for lyrics fetched from LRCLIB
- `Shift+C` shortcut to toggle lyric color quickly
- `Ctrl+R` shortcut to reload Spotify connection quickly

## Quick Start

1. Create a Spotify app in the Spotify Developer Dashboard.
2. Add this redirect URI:

```text
http://127.0.0.1:8888/callback
```

3. Copy the `Client ID` and `Client Secret`.
4. Install dependencies and run Lyricfy:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python src\main.py
```

5. Open Lyricfy settings and fill in:
   - Spotify Client ID
   - Spotify Client Secret
   - Redirect URI
6. Click `Save`, then click `Reload Spotify`.

## Requirements

- Windows
- Python 3.11 or newer
- A Spotify Premium account with active playback on a device
- A Spotify Developer app

## Project Structure

```text
.
|-- assets/
|   `-- lrc/
|-- src/
|   |-- main.py
|   `-- lyric_overlay/
|       |-- app_controller.py
|       |-- config.py
|       |-- lyrics.py
|       |-- main.py
|       |-- models.py
|       |-- overlay.py
|       |-- spotify_client.py
|       `-- sync_engine.py
|-- .env.example
|-- build.bat
|-- icon.ico
|-- Lyricfy.spec
|-- requirements.txt
`-- README.md
```

## Spotify App Setup

1. Open the Spotify Developer Dashboard.
2. Create a new app.
3. Add this redirect URI:

```text
http://127.0.0.1:8888/callback
```

4. Copy the `Client ID` and `Client Secret`.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Configuration

Lyricfy loads configuration from `.env`.

In development mode, runtime files stay in the project folder:

```text
.env
.spotify_cache
assets\lrc\
assets\lrc\downloaded\
```

In packaged `.exe` mode, runtime files are stored in:

```text
%APPDATA%\Lyricfy\
```

If no `.env` exists yet, Lyricfy creates one automatically with these defaults:

```env
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
POLL_INTERVAL_MS=1000
LRCLIB_ENABLED=true
AUTO_SAVE_FETCHED_LRC=true
LYRIC_OFFSET_MS=0
OVERLAY_BG_COLOR=#0A0A0AEB
OVERLAY_TEXT_COLOR=#F4F4F4
LYRIC_TEXT_COLOR=#F4F4F4
LYRIC_GLOW_COLOR=#66CCFFFF
```

Important runtime files:

- `.env`
- `.spotify_cache`
- `assets\lrc\`
- `assets\lrc\downloaded\`

## Run

Start the app with:

```powershell
python src\main.py
```

Do not run internal module files directly.

## Settings Panel

The built-in settings panel supports:

- Spotify Client ID
- Spotify Client Secret
- Redirect URI
- Lyric Offset (ms)
- Overlay Color
- Text Color
- Lyric Color
- Lyric Glow Color
- Auto-save fetched LRCLIB lyrics as local `.lrc` cache
- Clear downloaded lyric cache

Use `Save` to write changes to `.env`, then use `Reload Spotify` or press `Ctrl+R` to reconnect with the latest credentials.

## Lyric Offset

`Lyric Offset (ms)` shifts the displayed lyric timing:

- Negative values show lyrics earlier
- Positive values show lyrics later

Examples:

- `-250` shows lyrics 250 ms earlier
- `300` shows lyrics 300 ms later

## Local LRC Files

Place local lyric files in `assets/lrc/` with this naming format:

```text
Artist - Title.lrc
```

Example:

```text
Coldplay - Yellow.lrc
```

Example content:

```text
[00:10.00]Look at the stars
[00:13.50]Look how they shine for you
[00:18.20]And everything you do
```

Lyricfy sanitizes invalid Windows filename characters when matching local files.

Lyrics fetched from LRCLIB can be cached automatically as `.lrc` files in `assets/lrc/downloaded/`. This cache is reused on the next app launch and can be cleared from the settings panel.

If you want to disable this behavior, set `AUTO_SAVE_FETCHED_LRC=false` in `.env` or uncheck it in the settings panel and save.

## Build

Build the standalone executable with:

```powershell
build.bat
```

Output:

```text
dist\Lyricfy.exe
```

The build script packages the app as a one-file windowed executable and includes the application icon.

## Runtime Behavior

- The overlay opens near the top-center of the screen
- Closing the overlay hides it to the system tray instead of exiting
- Hiding the overlay pauses Spotify polling until the overlay is shown again
- The tray icon remains available for reopening settings or exiting the app
- If lyrics are available, the main line shows the current lyric and the second line shows `Title - Artist` briefly at the start of the song
- If lyrics are not available yet, the main line shows the track title and the second line shows the artist
- If lyric lookup still fails after automatic retries, the overlay briefly shows `No lyric found` and then returns to the title and artist view
- If playback is paused, the overlay shows a paused status
- If Spotify credentials are missing or invalid, the overlay prompts you to open settings

## Keyboard Shortcuts

- `Shift+C` toggles the lyric color mode quickly
- `Ctrl+R` reloads the Spotify connection without opening settings

## Notes

- Lyric sync is based on Spotify `progress_ms`
- External synced lyrics may not exactly match the track version currently playing
- Local `.lrc` files are the most reliable option when exact timing matters
- Spotify polling defaults to 1 second for faster track change detection
- Spotify API rate limiting is handled with a temporary cooldown message in the overlay

## Sources

- Spotify Web API for playback state
- LRCLIB for synced lyric fallback

## Author

Created by Stephanus Kevin Andika Rata  
Contact: kevinandika18@gmail.com
