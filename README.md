# Lyricfy

Lyricfy is a lightweight Spotify lyric overlay built with Python and PySide6. It reads local playback through Windows media sessions or Spotify's macOS scripting interface, syncs lyrics using local `.lrc` files or LRCLIB, and shows them in a compact always-on-top overlay.

Windows builds are validated locally. macOS support is implemented as a preview pending native playback, permissions, and desktop QA. See the [macOS validation checklist](docs/qa/macos-support.md) before treating it as a supported public release.

## Features

- Reads the currently playing track from Spotify
- Displays synced lyrics using Spotify playback progress
- Checks local `.lrc` files first, then falls back to LRCLIB
- Caches fetched LRCLIB lyrics as local `.lrc` files for future playback
- Reuses downloaded lyric cache across app restarts
- Batch-downloads `.lrc` files for Spotify liked songs and playlists with read-only API access
- Retries lyric lookup automatically when a new track does not resolve on the first attempt
- Compact frameless overlay that stays on top
- Three display presets: `Card Default`, `Floating Minimal`, and `Floating Context`
- Optional smaller next lyric below the active lyric
- Optional album artwork in Card and Floating modes, with automatic lyric-only fallback
- Floating artwork can stay visible or appear only when the overlay is hovered
- Configurable title and artist spacing below the lyric block
- Custom overlay corner radius from 0 to 40px
- Track information visibility options: on track change, always, or never
- Hover controls that respect individual Settings and Hide button preferences
- Smooth draggable overlay with stable positioning during lyric, artwork, hover, and monitor changes
- Small overlay position adjustments are accepted without snapping back to the previous position
- Compact Card and Floating overlays can sit partially beyond the left or right screen edge while keeping a 40px recovery area visible
- System tray controls for show, hide, settings, and exit
- System tray playback mode switch between `Non-API` and `API`
- In-app settings for display presets, artwork, Spotify credentials, lyric offset, alignment, font, and colors
- Local playback mode by default on Windows and macOS, without Spotify Developer credentials
- Auto-created `.env` file on first launch
- Separate Spotify token cache for packaged builds
- Automatic `.lrc` cache for lyrics fetched from LRCLIB
- Faster first window open by connecting to Spotify after the overlay is shown
- Displays `Fetching lyrics...` while lyric lookup is still in progress
- `Shift+C` shortcut to toggle between the lyric color and a custom toggle color quickly
- `Shift+S` shortcut to open or close settings quickly
- `Shift+F` shortcut to hide the overlay to tray quickly
- `Ctrl+R` (`Command+R` on macOS) shortcut to reload Spotify connection quickly
- `Shift+H` shortcut to return the overlay to the top-center of its current monitor

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

On macOS, use Terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

With Spotify running, allow the Automation request to read Spotify playback. A source run can show Terminal or Python as the requester; validate permissions again for the installed `.app`. If permission is denied, enable it in System Settings > Privacy & Security > Automation, then select `Reload Playback`. Lyricfy does not repeatedly request denied permission. Starting hidden defers the connection until you show the overlay or explicitly reload playback.

## Requirements

- Windows; macOS 13+ is the preview target (native validation pending)
- Python 3.11 or newer
- Spotify desktop app for local playback; Spotify Web API mode is also available
- Native macOS Python matching Apple Silicon (`arm64`) or Intel (`x86_64`) for Mac builds

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
|       |-- platform/
|       |-- spotify_client.py
|       `-- sync_engine.py
|-- .env.example
|-- build.bat
|-- build-macos.sh
|-- icon.ico
|-- icon.png
|-- Lyricfy-macos.spec
|-- packaging/windows.spec
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

In packaged macOS `.app` mode, writable runtime files are stored in:

```text
~/Library/Application Support/Lyricfy/
```

This folder contains `.env`, `.spotify_cache`, and `assets/lrc/` (including `downloaded/`). Bundled images and scripts remain inside the app; settings and caches are never written into the bundle. macOS diagnostics rotate in `~/Library/Logs/Lyricfy/lyricfy.log`.

If no `.env` exists yet, Lyricfy creates one automatically with these defaults:

```env
PLAYBACK_SOURCE=local
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
LYRIC_FONT_FAMILY=system
LYRIC_FONT_SIZE=11
TEXT_ALIGNMENT=left
DISPLAY_STYLE=card
LYRIC_LINES=single
TRACK_INFO_MODE=track_change
SHOW_ALBUM_COVER=false
FLOATING_COVER_MODE=always
TRACK_INFO_GAP_PX=4
OVERLAY_CORNER_RADIUS=30
SHOW_SETTINGS_BUTTON=true
SHOW_HIDE_BUTTON=true
HOVER_BUTTONS_ENABLED=false
AUTOSTART_ENABLED=false
AUTOSTART_START_HIDDEN=false
```

`system` uses the macOS application font or Segoe UI on Windows. Newly generated Windows settings retain `Segoe UI`; existing font choices are preserved, with a system fallback for fonts unavailable on macOS. Legacy `PLAYBACK_SOURCE=windows` values load as `local` and are normalized on the next settings save.

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

The downloader remains a separate source CLI on both platforms; it is not included in the GUI executable or `.app`. To reuse its downloads in a packaged app, copy the `.lrc` files into that app's writable `assets/lrc/downloaded/` folder described above.

If Spotify login was already cached before these read-only scopes were added, delete `.spotify_cache` and run the downloader again to authorize the updated scopes.

## Settings Panel

The built-in settings panel supports:

- Display presets: `Card Default`, `Floating Minimal`, and `Floating Context`
- Detailed display controls for card/floating style, single/current-next lyrics, and track information visibility

- Automatically hides Spotify API credential fields while `Non-API` mode is active
- Spotify Client ID
- Spotify Client Secret
- Redirect URI
- Lyric Offset (ms)
- Text Alignment
- Display Preset
- Display Style
- Lyric Lines
- Track Information
- Track Info Gap (`0` to `24` px, default `4` px)
- Lyric Font
- Font Size
- Overlay Color
- Text Color
- Lyric Color
- Lyric Glow Color
- Optional album cover in Card and Floating modes
- Floating cover visibility (`Always Visible` or `On Hover`)
- Overlay corner radius (`0` to `40` px)
- Auto-save fetched LRCLIB lyrics as local `.lrc` cache
- Shortcut guide
- Reset Default
- Clear downloaded lyric cache
- Close Settings

Use `Save` to write changes to `.env`, then use `Reload Playback` or press `Ctrl+R` (`Command+R` on macOS) to reconnect with the latest credentials. API login opens a browser with a bounded loopback callback wait. Cancellation, a busy callback port, or login timeout is reported in the overlay; retry with `Reload Playback`.

### Display Presets

- `Card Default` keeps the original rounded lyric card with one active lyric line.
- `Floating Minimal` hides the card and track information so only the active lyric remains. A subtle background and the overlay buttons appear on hover.
- `Floating Context` adds the next lyric below the active lyric in a smaller, dimmer style.
- `Track Info Gap` controls the space before the title and artist. It updates the overlay preview immediately and remains adaptive when lyrics wrap to two lines.
- Floating presets always show Settings and Hide controls on hover. `Card Controls on Hover` only changes the behavior of `Card Default`.
- Changing the detailed display controls to a combination that does not match a built-in preset is shown as `Custom`.
- Opening Settings always restores the full card temporarily so the controls remain readable.

### Album Cover

- Album artwork is optional and disabled by default.
- Enable `Show album cover` in Settings to place a 48px rounded cover beside the lyrics.
- Spotify API mode uses the album image URL from Spotify; Non-API mode uses artwork exposed by the Windows media session or Spotify's macOS scripting interface when available.
- If artwork is loading, missing, or invalid, Lyricfy automatically keeps the normal lyric-only layout without a placeholder or error.
- Floating presets can keep artwork `Always Visible` or show it only `On Hover`.
- Artwork and the lyric block remain vertically centered with each other in every display mode, including wrapped lyrics and `Current + Next`.
- Artwork keeps its compact rounded corners and disappears without leaving a gap when unavailable.

### Overlay Corner Radius

- `Overlay Corner Radius` controls the rounded corners of the Card background, Settings background, and subtle Floating hover background.
- The supported range is `0` to `40` pixels. `0` produces square corners and the default remains `30` pixels.
- Album artwork keeps its own fixed 8px corner radius.

`Floating Cover` and `Overlay Corner Radius` are grouped under the left-side `Overlay` section so the Settings columns remain balanced.

`PLAYBACK_SOURCE` supports:

- `local` for Windows media sessions or macOS Spotify scripting, selected automatically by OS
- `windows` as a backward-compatible alias for `local`
- `spotify_api` for the Spotify Web API flow

You can also change the mode from the tray menu:

- `Show Overlay`
- `Hide Overlay`
- `Open Settings`
- `Snap Home` -> return the overlay to top-center on its current monitor
- `Mode` -> `Non-API` or `API`
- `Overlay Controls` -> show or hide the overlay controls and enable `Card Controls on Hover`
- `Startup` -> enable login startup and choose whether Lyricfy opens visible or starts hidden in the tray/menu bar
- `Display Preset` -> `Card Default`, `Floating Minimal`, or `Floating Context`
- `Lyricfy v1.4.2`

Recommended value:

```env
POLL_INTERVAL_MS=1000
```

This keeps Spotify playback detection responsive without polling too aggressively.

### macOS Menu Bar and Login Startup

The macOS app uses a menu bar icon with Show, Hide, Settings, mode selection, and Quit. It does not normally display a Dock icon. If the tray/menu bar is unavailable, the overlay stays visible and its close control quits the app.

Install `Lyricfy.app` in `/Applications` or `~/Applications` before enabling Auto Start. Lyricfy registers `~/Library/LaunchAgents/com.lyricfy.overlay.plist` for the next login. Enabling it does not launch a second copy immediately. Source runs and apps in Downloads or mounted DMGs cannot enable it. If the app is moved after registration, install it in Applications and turn Auto Start off and on to repair the path.

macOS may independently disable a registered item in System Settings > General > Login Items. Lyricfy reports registration rather than claiming OS permission. It does not rewrite the registration on each app launch. Test visible and hidden startup after a real logout/login before release.

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

Build on the target OS: Windows creates `.exe`; macOS creates `.app`, `.zip`, and `.dmg`. The same Python source supports both. A Windows machine can obtain Mac artifacts through the macOS jobs in [GitHub Actions](.github/workflows/build.yml) once the changes are pushed and the workflow has run.

### Windows

Build the standalone executable with:

```powershell
build.bat
```

Output:

```text
dist\Lyricfy.exe
```

The build script packages the app as a one-file windowed executable and includes the application icon.

The tracked build input is `packaging/windows.spec`. For a non-interactive build:

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean packaging/windows.spec
```

### macOS Preview

After installing dependencies in a native Mac virtual environment:

```bash
source .venv/bin/activate
bash build-macos.sh
```

The script generates the ICNS icon from tracked `icon.png`, builds the bundle, verifies its signature, runs an offscreen startup smoke test, and creates archives with checksums under `dist/macos-arm64/` or `dist/macos-x86_64/`. Default preview builds use ad-hoc signing and are not notarized public releases. Build each architecture with its native Python; there is no Windows-to-macOS cross-compilation or universal2 output.

### macOS Signed Release

After native QA, use a Mac with a Developer ID Application certificate/private key installed and a configured `notarytool` keychain profile:

```bash
export LYRICFY_CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'
export LYRICFY_NOTARY_PROFILE='lyricfy-notary'
bash build-macos.sh --release
```

Release mode signs with hardened runtime and the Apple Events entitlement, requires notarization acceptance, staples tickets, and checks Gatekeeper assessment for the app and DMG. Credentials stay in the keychain. The default CI workflow builds previews without signing secrets. Validate the downloaded release on a clean Mac account as described in the [QA checklist](docs/qa/macos-support.md).

### Automated Checks

```text
python -m pip check
python -m pytest -q
```

GitHub Actions runs tests and builds on Windows, macOS Apple Silicon, and macOS Intel, using Python 3.11 and recording the exact version. Download the matching preview artifact from the workflow run. These checks verify imports and bundle startup; interactive Spotify, Automation, Spaces, and login behavior still require native QA.

## Runtime Behavior

- The overlay opens near the top-center of the screen
- The overlay can appear first and continue connecting to Spotify in the background during startup
- Closing the overlay hides it to the system tray/menu bar; without a tray, closing quits
- Hiding the overlay pauses Spotify polling until the overlay is shown again
- The tray icon remains available for reopening settings or exiting the app
- The app starts in `Non-API` mode by default unless you explicitly saved `API` mode in `.env`
- If lyrics are available, the main line shows the current lyric and the second line shows `Title - Artist` briefly at the start of the song
- If lyrics are not available yet, the main line shows the track title and the second line shows the artist
- While lyric lookup is still running or retrying, the overlay shows `Fetching lyrics...`
- If lyric lookup still fails after automatic retries, the overlay briefly shows `No lyric found` and then returns to the title and artist view
- If playback is paused, the overlay shows a paused status
- If Windows media session access is unavailable, the overlay prompts you to open Spotify desktop and retry
- macOS local mode leaves Spotify closed if it is not running and distinguishes denied Automation permission from transient playback failures

## Keyboard Shortcuts

- `Shift+C` toggles between the lyric color and the custom toggle lyric color
- `Shift+S` opens or closes the settings panel
- `Shift+F` hides the overlay to the system tray
- `Ctrl+R` (`Command+R` on macOS) reloads the Spotify connection without opening settings
- `Shift+H` snaps the overlay to its top-center home position on the current monitor
- Compact mode may be positioned partly off-screen; Settings stays fully visible and `Shift+H` restores the overlay if needed

## Notes

- Lyric sync is based on Spotify `progress_ms`
- External synced lyrics may not exactly match the track version currently playing
- Local `.lrc` files are the most reliable option when exact timing matters
- Spotify polling defaults to 1 second for faster track change detection
- Spotify API rate limiting is handled with a temporary cooldown message in the overlay

## Sources

- Windows Global System Media Transport Controls session for playback state
- Spotify's macOS scripting dictionary through JXA/Apple Events for local Mac playback
- LRCLIB for synced lyric fallback

## Author

Created by Stephanus Kevin Andika Rata  
Contact: kevinandika18@gmail.com
