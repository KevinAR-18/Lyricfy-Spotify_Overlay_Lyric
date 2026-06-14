# Lyricfy

Lyricfy is a lightweight Windows lyric overlay for Spotify built with Python and PySide6. It reads the current track from the local Windows media session by default, syncs lyrics using local `.lrc` files or LRCLIB, and shows them in a compact always-on-top overlay.

## Features

- Reads the currently playing track from Spotify
- Displays synced lyrics using Spotify playback progress
- Checks local `.lrc` files first, then falls back to LRCLIB
- Caches fetched LRCLIB lyrics as local `.lrc` files for future playback
- Reuses downloaded lyric cache across app restarts
- Batch-downloads `.lrc` files for Spotify liked songs and playlists with read-only API access
- Retries lyric lookup automatically when a new track does not resolve on the first attempt
- Compact frameless overlay that stays on top
- Draggable overlay with snap-back behavior near the last saved position
- System tray controls for show, hide, settings, and exit
- System tray playback mode switch between `Non-API` and `API`
- In-app settings for Spotify credentials, redirect URI, lyric offset, alignment, font, and colors
- Windows local playback mode by default on startup, without Spotify Developer credentials
- Auto-created `.env` file on first launch
- Separate Spotify token cache for packaged builds
- Automatic `.lrc` cache for lyrics fetched from LRCLIB
- Faster first window open by connecting to Spotify after the overlay is shown
- Displays `Fetching lyrics...` while lyric lookup is still in progress
- `Shift+C` shortcut to toggle between the lyric color and a custom toggle color quickly
- `Shift+S` shortcut to open or close settings quickly
- `Shift+F` shortcut to hide the overlay to tray quickly
- `Ctrl+R` shortcut to reload Spotify connection quickly

## Quick Start

1. Install dependencies and run Lyricfy:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python src\main.py
```

2. Open Spotify desktop and start playback.
3. Lyricfy should detect the current track automatically.

## Requirements

- Windows
- Python 3.11 or newer
- Spotify desktop app running on Windows

## Project Structure

```text
.
|-- assets/
|   `-- lrc/
|-- src/
|   |-- download_spotify_lrc.py
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

## Spotify API Mode Setup

1. Open the Spotify Developer Dashboard.
2. Create a new app.
3. Add this redirect URI:

```text
http://127.0.0.1:8888/callback
```

4. Copy the `Client ID` and `Client Secret`.

The batch `.lrc` downloader uses these Spotify read-only scopes:

```text
user-library-read playlist-read-private playlist-read-collaborative
```

These scopes allow Lyricfy to read liked songs and playlists. They do not allow creating, editing, deleting, or adding tracks to playlists.

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
PLAYBACK_SOURCE=windows
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
LYRIC_TOGGLE_COLOR=#1A1A1A
LYRIC_FONT_FAMILY=Segoe UI
LYRIC_FONT_SIZE=11
TEXT_ALIGNMENT=left
SHOW_SETTINGS_BUTTON=true
SHOW_HIDE_BUTTON=true
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

## Spotify Library LRC Downloader

Lyricfy includes a separate CLI tool for downloading synced `.lrc` files from LRCLIB based on your Spotify liked songs and playlists.

Run a small test first:

```powershell
python src\download_spotify_lrc.py --limit 5
```

Download for all readable liked songs and playlists:

```powershell
python src\download_spotify_lrc.py
```

Useful options:

```powershell
python src\download_spotify_lrc.py --source liked
python src\download_spotify_lrc.py --source playlists
python src\download_spotify_lrc.py --limit 50
python src\download_spotify_lrc.py --no-report
```

The downloader:

- Reads Spotify data only; it does not modify your account or playlists
- Deduplicates songs by Spotify track ID
- Skips `.lrc` files that already exist
- Saves downloaded files to `assets\lrc\downloaded\`
- Writes a JSON report to `assets\lrc\downloaded\lrc_download_report.json` by default

If Spotify login was already cached before these read-only scopes were added, delete `.spotify_cache` and run the downloader again to authorize the updated scopes.

## Settings Panel

The built-in settings panel supports:

- Automatically hides Spotify API credential fields while `Non-API` mode is active
- Spotify Client ID
- Spotify Client Secret
- Redirect URI
- Lyric Offset (ms)
- Text Alignment
- Lyric Font
- Font Size
- Overlay Color
- Text Color
- Lyric Color
- Lyric Glow Color
- Auto-save fetched LRCLIB lyrics as local `.lrc` cache
- Shortcut guide
- Reset Default
- Clear downloaded lyric cache
- Close Settings

Use `Save` to write changes to `.env`, then use `Reload Playback` or press `Ctrl+R` to reconnect with the latest credentials.

`PLAYBACK_SOURCE` supports:

- `windows` for local Windows media session playback detection
- `spotify_api` to force the previous Spotify Web API flow

You can also change the mode from the tray menu:

- `Show Overlay`
- `Hide Overlay`
- `Open Settings`
- `Mode` -> `Non-API` or `API`
- `Overlay Buttons` -> show or hide the `Settings` and `Hide` buttons on the overlay
- `Lyricfy v1.3.1`

Recommended value:

```env
POLL_INTERVAL_MS=1000
```

This keeps Spotify playback detection responsive without polling too aggressively.

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

If an LRCLIB exact lookup fails because of a network timeout or request error, Lyricfy can retry using a narrower search fallback before giving up.

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
- The overlay can appear first and continue connecting to Spotify in the background during startup
- Closing the overlay hides it to the system tray instead of exiting
- Hiding the overlay pauses Spotify polling until the overlay is shown again
- The tray icon remains available for reopening settings or exiting the app
- The app starts in `Non-API` mode by default unless you explicitly saved `API` mode in `.env`
- If lyrics are available, the main line shows the current lyric and the second line shows `Title - Artist` briefly at the start of the song
- If lyrics are not available yet, the main line shows the track title and the second line shows the artist
- While lyric lookup is still running or retrying, the overlay shows `Fetching lyrics...`
- If lyric lookup still fails after automatic retries, the overlay briefly shows `No lyric found` and then returns to the title and artist view
- If playback is paused, the overlay shows a paused status
- If Windows media session access is unavailable, the overlay prompts you to open Spotify desktop and retry

## Keyboard Shortcuts

- `Shift+C` toggles between the lyric color and the custom toggle lyric color
- `Shift+S` opens or closes the settings panel
- `Shift+F` hides the overlay to the system tray
- `Ctrl+R` reloads the Spotify connection without opening settings

## Notes

- Lyric sync is based on Spotify `progress_ms`
- External synced lyrics may not exactly match the track version currently playing
- Local `.lrc` files are the most reliable option when exact timing matters
- Spotify polling defaults to 1 second for faster track change detection
- Spotify API rate limiting is handled with a temporary cooldown message in the overlay

## Sources

- Windows Global System Media Transport Controls session for playback state
- LRCLIB for synced lyric fallback

## Author

Created by Stephanus Kevin Andika Rata  
Contact: kevinandika18@gmail.com
