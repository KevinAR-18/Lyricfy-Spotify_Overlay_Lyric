# macOS validation record

Status as of 2026-09-05: implementation and build automation are available;
native macOS validation has not run. Do not advertise a validated Mac release
based only on the Windows tests or synthetic Spotify snapshots.

## Evidence available

| Check | Result |
| --- | --- |
| Windows development environment | Python 3.12.5, PySide6 6.11.0, PyInstaller 6.19.0 |
| Dependency consistency | `python -m pip check` passed on Windows |
| Automated tests | 163 passed, 1 native macOS test skipped on Windows |
| Windows packaging | `packaging/windows.spec` built `dist/verification-windows/Lyricfy.exe` |
| Packaged Windows startup | `Lyricfy.exe --smoke-test` passed with Qt offscreen; exit 0 |
| Static checks | Python/spec syntax, entitlements plist, Bash syntax, JXA syntax and `git diff --check` passed |
| macOS dependency install, tests and native bundles | Pending CI/native Mac execution |
| Spotify dictionary, TCC, window manager and login | Pending interactive Mac QA |
| Developer ID, notarization and quarantined download | Pending credentials and native release QA |

The build workflow targets Python 3.11 on Windows, macOS arm64 and macOS x86_64.
Record its run URL and exact Python patch version when executed. macOS 13+ is
the intended floor; a successful macOS 15 build does not verify macOS 13.

## Native scripting validation (first Mac gate)

Use an interactive Mac with Spotify installed. Record `sw_vers`, `uname -m`,
`python3 -VV`, Spotify version, app version, architecture, signature type, and
how the app was launched. Capture the installed dictionary before accepting
the script's property names or time units:

```bash
mkdir -p build/native-qa
sw_vers > build/native-qa/macos.txt
uname -m > build/native-qa/architecture.txt
python3 -VV > build/native-qa/python.txt
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' \
  /Applications/Spotify.app/Contents/Info.plist > build/native-qa/spotify-version.txt
/usr/bin/sdef /Applications/Spotify.app > build/native-qa/spotify.sdef
```

Adjust only the Spotify installation path if it differs. The checked-in script
expects track `name`, `artist`, `album`, `id`, `duration`, and `artworkUrl`, plus
application `playerState` and `playerPosition`. Confirm that duration is in
milliseconds and position is in seconds against a song with a known length.
Verify a 10-second seek moves `position_seconds` by approximately 10.

With Spotify closed, run the native no-launch test:

```bash
python -m pytest tests/test_macos_native.py -q
```

Then open Spotify, play a song, and capture a snapshot (this Terminal run can
request Automation consent independently of the packaged app):

```bash
/usr/bin/osascript -l JavaScript \
  src/lyric_overlay/platform/spotify_snapshot.js > build/native-qa/playing.json
```

Repeat with paused playback, a seek, a track change, a local file, a podcast,
missing artwork, Spotify stopped, and denied permission. Keep metadata captures
local until reviewed for personal information; add sanitized recorded fixtures
to tests only after verifying them. Current unit fixtures are synthetic.
Denial should produce `permission_denied`, not an endless request loop.

## Bundle and permission checks

- [ ] Run `bash build-macos.sh` on native arm64; repeat on Intel before
  advertising Intel support. Save build logs and dependency versions.
- [ ] Inspect `Info.plist`: `com.lyricfy.overlay`, expected version, `LSUIElement`,
  `LSMinimumSystemVersion`, and the Spotify Automation usage description.
- [ ] Confirm the bundle contains the JXA script, PNG, ICNS, template SVG,
  required Qt Cocoa/image plugins, and no `.env`, Spotify cache or Windows SDK.
- [ ] Extract the ZIP or mount the DMG and copy the app to Applications. Launch
  it from Finder without Python, the checkout or a development shell.
- [ ] Verify menu bar icon contrast in light/dark appearance, app name and icon,
  absence of a normal Dock icon, Show/Hide/Settings/Quit, and duplicate launches.
- [ ] Allow Spotify Automation from the installed app; verify title, artist,
  playback position and artwork. Record the requester shown by macOS.
- [ ] Deny permission, confirm one actionable error, allow it in System Settings
  > Privacy & Security > Automation, then Reload Playback. Repeat after update.
- [ ] Start hidden with Spotify running; verify no query or permission/browser
  prompt until Show Overlay, Open Settings, or explicit Reload Playback.
- [ ] Hide, reload and quit while scripting or OAuth is waiting. Verify no
  leftover `osascript` process, duplicate worker or stale lyric update.

## Shared features and desktop behavior

- [ ] Play/pause, repeat, forward/backward seek, track changes, missing/unknown
  duration, local files, podcasts/ads, Spotify quit/relaunch, and sleep/wake.
- [ ] Local `.lrc`, LRCLIB lookup/cache/retry, lyric offset and downloaded-cache
  clearing; check timed lyrics against more than one known song.
- [ ] API mode with valid/invalid credentials, a cached/expired token, declined
  browser login, timeout/cancellation, occupied loopback port, lost network,
  denied API access and rate-limit recovery. No console input is required.
- [ ] Every display preset, cover mode, missing artwork, color, font, size,
  alignment, settings persistence and migration from `PLAYBACK_SOURCE=windows`.
- [ ] Command+R and the Shift shortcuts while focused; hide/show, Snap Home,
  partial-edge placement and settings accessibility.
- [ ] Retina/mixed-DPI monitors, monitor removal, drag across screens, Spaces,
  fullscreen, Mission Control and Stage Manager. Record limits on topmost
  behavior; do not promise visibility over all macOS system UI.
- [ ] Without a usable tray/menu bar, startup stays visible and Close quits.
- [ ] Run the separate source batch downloader; copy its `.lrc` output from the
  repository into the packaged app's `assets/lrc/downloaded/` and verify reuse.

## Login startup, data and uninstall

- [ ] From `/Applications` and `~/Applications` (including a path with spaces),
  enable Auto Start. Verify `~/Library/LaunchAgents/com.lyricfy.overlay.plist`
  points to the installed app and enabling it does not immediately launch again.
- [ ] Log out and in for both visible and hidden choices. Confirm only one app,
  and no Spotify launch or prompts while hidden. Quit must not relaunch it.
- [ ] Disable Auto Start; verify the job is unloaded, its plist removed, and no
  unrelated LaunchAgent modified. Repeat when the job is already unloaded.
- [ ] Disable the item through System Settings > General > Login Items. Confirm
  Lyricfy does not re-register it during ordinary startup; registration alone
  is not a claim that macOS authorizes background launch.
- [ ] Try source, Downloads, mounted DMG and translocated app locations: enabling
  login startup must request installation in Applications instead.
- [ ] Move or update the app. Confirm path repair instructions, no duplicates,
  and retained `.env`, token cache and lyrics under
  `~/Library/Application Support/Lyricfy/`.
- [ ] Check bounded diagnostics in `~/Library/Logs/Lyricfy/`; no credentials,
  tokens or callback URLs should be logged.
- [ ] Disable Auto Start before removing the app. Removing/replacing the bundle
  retains data. Optional removal of the user's Lyricfy data/log folders is a
  separate explicit user decision.

## Public release gate

After preview QA, build with `bash build-macos.sh --release` using Developer ID
and a notarytool keychain profile as described in the README. For each supported
architecture, save these results and the notarization submission IDs:

```bash
codesign --verify --deep --strict /Applications/Lyricfy.app
codesign -d --entitlements :- /Applications/Lyricfy.app
spctl --assess --type execute --verbose=2 /Applications/Lyricfy.app
xcrun stapler validate /Applications/Lyricfy.app
```

- [ ] Validate the final DMG signature, accepted notarization and stapled ticket.
- [ ] Download the actual release on a clean account, keeping its quarantine
  attribute. Install and open through Finder without Gatekeeper workarounds.
- [ ] Repeat offline after download to exercise the stapled ticket.
- [ ] Repeat Spotify Automation and login startup under the production signature.
- [ ] Test the advertised minimum macOS version and both advertised architectures.

Record one row per tested combination:

| Date | macOS | CPU | Python/dependencies | Spotify | Artifact/version/hash | Launch method | Result/limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pending | | | | | | | |
