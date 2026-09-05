# macOS Support Plan

Status: code and build automation implemented; Windows build/startup verified.
Native macOS preview validation and signed release gates remain open.
Implemented on `feature/macos-support` on 2026-09-05.

## Execution Record

- Shared platform selection, legacy config migration, macOS JXA playback,
  cancellable polling/OAuth, platform autostart, menu bar, fonts, writable paths,
  and diagnostics are implemented.
- Platform-specific dependencies and tests are split. Windows verification:
  163 tests passed, 1 native macOS test skipped; `pip check` passed with Python
  3.12.5, PySide6 6.11.0 and PyInstaller 6.19.0.
- The tracked Windows spec produced
  `dist/verification-windows/Lyricfy.exe`; the packaged offscreen startup test
  exited successfully. Existing Windows local playback tests are retained.
- Native macOS build/sign/notarize scripts and a Windows/arm64/Intel CI matrix
  are prepared. The ICNS is generated reproducibly from tracked `icon.png`
  using Apple's `sips`/`iconutil` during a Mac build; the menu bar SVG is tracked.
- README instructions and the [native QA record](../qa/macos-support.md) cover
  both platforms, preview limitations, login startup and release gates.
- This execution environment is Windows. Phase 0's installed Spotify dictionary,
  real snapshots and TCC proof could not be collected before implementation;
  current parser fixtures are synthetic. Run that gate first on a Mac and
  adjust the adapter if the installed dictionary disagrees.
- macOS dependency installation, native builds, Finder/Spotify/Spaces/login QA,
  and production signing/notarization have not run. The CI workflow must be
  pushed and executed before its results can be claimed. Prepared automation
  does not complete those acceptance criteria.

## Objective

Support Windows and macOS from one Lyricfy codebase while retaining the current
feature set: local Spotify playback detection without API credentials, Spotify
API playback, synced lyrics, album art, overlay controls, tray controls,
shortcuts, saved settings, and autostart.

Deliver a working development bundle first, then a signed/notarized public
release. Mocked tests alone do not establish native macOS compatibility.

## Starting State (Before Implementation)

Lyricfy is a Python and PySide6 desktop application. Its UI, lyric handling,
sync engine, Spotify Web API client, and cover-art repository can be shared,
but their macOS runtime behavior still needs validation. Integration points:

- `spotify_client.py` already defines `PlaybackClient` and imports `winsdk`
  lazily inside the Windows client. Its factory still selects Windows for
  local playback on every OS.
- `set_windows_autostart` in `src/lyric_overlay/main.py` writes the Windows Run
  Registry key through `winreg`, silently ignoring unsupported platforms and
  write failures. Startup, Settings, and tray actions call it directly.
- `src/lyric_overlay/config.py` stores packaged application data in `%APPDATA%`.
  It falls back to `~/.lyricfy`; packaged `BASE_DIR` points beside the executable.
  Config defaults, `.env.example`, and UI state assume `PLAYBACK_SOURCE=windows`.
- `src/lyric_overlay/overlay.py` contains optional Win32 and DWM calls to remove
  native framing and preserve topmost behavior; these are already guarded.
  Segoe UI fonts, startup text, and window hide/restore behavior need review.
- `PlaybackWorker.stop()` joins for 1.5 seconds then discards the thread
  reference, which could leave a longer scripting query active. Hidden startup
  also schedules initialization that starts polling.
- `build.bat` targets Windows. `Lyricfy.spec` and the InstallForge project are
  ignored local artifacts, not tracked build inputs available in a fresh clone.
  Both `icon.ico` and `icon.png` are tracked.
- `requirements.txt` installs Windows-only packages without platform markers.
- `tests/test_spotify_client.py` imports `winsdk` at module import time.
- The batch downloader is a separate source CLI, not a GUI-bundle feature.
  No CI workflow is currently tracked.

## Supported Baseline

| Area | Initial target |
| --- | --- |
| Windows | Preserve existing supported installation and build behavior |
| macOS | macOS 13+, subject to the final bundled dependencies |
| Python | CPython 3.11 as the initial build/test baseline; record the exact patch version |
| Dependencies | Begin with the current PySide6 6.11.0 and PyInstaller 6.19.0 pins |
| Architectures | Separate native arm64 and x86_64 artifacts; validate arm64 first |
| Installation | `.app` installed in `/Applications` or `~/Applications` |

The macOS floor follows [Qt 6.11 support](https://doc.qt.io/qt-6.11/supported-platforms.html)
and [PySide6 6.11.0 wheel metadata](https://pypi.org/project/PySide6/6.11.0/).
Verify Python, Essentials, Addons, Shiboken, and collected libraries as well;
setting `LSMinimumSystemVersion` does not lower their actual requirements.
Only advertise tested combinations. If Intel validation is unavailable, label
the first preview arm64-only. Defer universal2 until every native dependency
and both execution architectures are validated.

## Design Decisions

### One Shared Codebase

Do not create a separate macOS application repository. Keep UI, application
logic, lyric handling, and API playback shared. Isolate only OS integrations:

```text
src/lyric_overlay/
|-- platform/
|   |-- __init__.py
|   |-- playback_windows.py
|   |-- playback_macos.py
|   |-- autostart_windows.py
|   `-- autostart_macos.py
|-- spotify_client.py            # Existing protocol, API client, playback factory
|-- app_controller.py            # Shared polling and worker lifecycle
|-- config.py
|-- main.py
`-- overlay.py
```

Preserve Windows playback, Registry command quoting, and native window behavior.
Select local backends explicitly for `sys.platform == "win32"` and `"darwin"`,
using lazy imports without cycles between the factory and backends. Package
initializers must not import foreign native bindings. Use qualified imports for
`lyric_overlay.platform` to avoid shadowing Python's standard `platform` module.
On other OSes, report unsupported local playback; API selection remains
independent of the OS. Do not silently substitute an API client.

### Configuration Compatibility

Introduce `local` as the canonical platform-neutral playback source:

| Loaded `PLAYBACK_SOURCE` | Normalized value | Behavior |
| --- | --- | --- |
| `local` | `local` | Select the current OS's local client |
| `windows` | `local` | Accept existing configs, including one copied to a Mac |
| `spotify_api` | `spotify_api` | Preserve explicit API selection |
| Missing, empty, invalid | `local` | Preserve the current fallback-to-local policy |

Normalize case/whitespace in one place. Update defaults, save/load, the factory,
`.env.example`, Settings/tray state, and tests together. Save canonical values
on the next normal settings save without resetting credentials or other values.

### Playback Modes

The existing two user-visible modes remain:

| Mode | Windows | macOS |
| --- | --- | --- |
| Non-API | Windows Global System Media Transport Controls (`winsdk`) | Spotify desktop scripting via `/usr/bin/osascript` |
| API | Spotify Web API through Spotipy | Spotify Web API through Spotipy |

Non-API mode observes Spotify desktop; browser playback and arbitrary Spotify
Connect devices are not promised. Reading local playback needs no API
credentials, but LRCLIB and artwork downloads still require connectivity.
The batch downloader remains API-authenticated even when the GUI uses Non-API.

Implement `MacSpotifyClient` against Spotify's installed scripting dictionary,
verified in Phase 0, returning the existing `TrackInfo`. Collect title, artist,
album, stable ID, duration, position, playing state, and optional artwork URL.
Record actual property names and time units in fixtures; test seconds-to-ms
conversion separately from values already in milliseconds.

The macOS implementation must handle all normal unavailable states without
crashing the polling worker:

- Spotify is not installed or not running.
- Spotify is running but there is no current track.
- Spotify is paused, stopped, or playing an advertisement/podcast with missing
  optional metadata.
- macOS denies the Apple Events Automation permission.
- `osascript` times out or returns malformed data.

Use one checked-in static script per snapshot query, bundled as a resource.
Prefer JXA (`osascript -l JavaScript`) and `JSON.stringify` for versioned UTF-8
JSON, avoiding handwritten delimiter escaping. It uses the same app scripting
interface as AppleScript; Apple documents both languages in its
[Mac Automation Scripting Guide](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/index.html).

- Invoke the absolute executable using an argument list and `shell=False`;
  keep metadata out of script source and capture stdout/stderr separately.
- Check installation/running state without launching or activating Spotify or
  using System Events UI scripting. A regular AppleScript `tell` can otherwise
  [launch its target](https://developer.apple.com/library/archive/documentation/AppleScript/Conceptual/AppleScriptLangGuide/reference/ASLR_control_statements.html).
- Define schema version, availability/error status, and track fields. Validate
  types and finite numeric values, cap output size, clamp negative positions
  and positions beyond a known duration. Test quotes, tabs, newlines,
  backslashes, emoji, and non-Latin metadata.
- Prefer the Spotify identifier/URI; otherwise use a deterministic namespaced
  identity from normalized artist, title, album, and duration. Exclude progress,
  playing state, and artwork; do not use Python's randomized `hash()`.
- Discard inconsistent snapshots when the track changes mid-query. Missing
  artwork/album must not discard an otherwise usable track. Use `cover_url`
  with the shared cover repository, keeping downloads out of playback polling.

| Condition | Required outcome |
| --- | --- |
| Spotify absent, closed, stopped, or no usable current track | `None`; clear obsolete lyrics/artwork; keep Spotify closed |
| Paused with valid metadata | Return the track with frozen position and `is_playing=False` |
| Advertisement, podcast, or local file with incomplete metadata | Handle missing fields or return `None`; never reuse the previous song's lyrics |
| Automation denied | Distinct recoverable permission error and instructions |
| Timeout, process exit, malformed reply | Bounded failure, retry/backoff, and a surviving polling worker |

Safe handling of podcasts/advertisements does not imply lyric support. Do not
turn every failure into `None`, since denial needs different recovery from
ordinary absence of playback. API mode remains an explicit alternative with
credentials, authorized account access, network, and Spotify
[rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits)
and [quota restrictions](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).

### Polling, Permissions, and Lifecycle

Keep the 1-second default poll interval and 50-ms render timer. Interpolate in
the controller without double-counting time in the adapter; re-anchor on seek,
resume, track changes, sleep/wake, and Show. Handle unknown duration without
clamping estimated progress to zero in `_estimated_progress_ms`.

Normal script queries should have a short timeout (initial target: 2 seconds).
First authorization needs a separate cancellable interaction with a longer
bounded wait (initial target: 30 seconds) so the user can answer the prompt.
Both run off the GUI thread. After denial, suspend permission attempts until
explicit reconnect. Transient failures use capped backoff; stale lyrics must
not continue advancing indefinitely.

Worker cleanup must cancel/reap an active Mac subprocess. Do not discard a live
thread after the existing 1.5-second join, overlap polls, or apply queued events
from an old connection. Test cancellation and a stale-event guard during
reconnect, mode switches, Hide, and Quit, including pending permission prompts.

Hidden startup must defer polling and permission/OAuth prompts until Show or an
explicit connection action. Fix the current unconditional deferred initialization
path. Hiding stops polling; showing resumes exactly one worker with fresh data.

Include a stable `CFBundleIdentifier` (`com.lyricfy.overlay`), explanatory
`NSAppleEventsUsageDescription`, and the
`com.apple.security.automation.apple-events` entitlement for hardened-runtime
signing. These requirements come from Apple's
[usage-description documentation](https://developer.apple.com/documentation/bundleresources/information-property-list/nsappleeventsusagedescription)
and [Apple Events entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.automation.apple-events).

Test consent attribution from Finder, login startup, and the signed bundle;
Terminal success alone is insufficient. Development consent may belong to the
launcher. Explain recovery through System Settings > Privacy & Security >
Automation, then Reconnect, following Apple's
[permission guide](https://support.apple.com/en-euro/guide/mac-help/mchl108e1718/mac).
The design does not require Accessibility permission or UI automation.

### User Data and Resources

For packaged builds, store writable Lyricfy data in native per-user locations:

| Platform | Data location |
| --- | --- |
| Windows | `%APPDATA%\Lyricfy`, retaining the existing home fallback |
| macOS | `~/Library/Application Support/Lyricfy` |

This includes `.env`, Spotify OAuth token cache, local and downloaded `.lrc`
files, and lyric-download reports. Development mode continues to use the
repository base directory so the current developer flow does not change.

Branch by OS before reading `APPDATA`. Never derive writable paths from the
working directory, `_MEIPASS`, or `Lyricfy.app/Contents/MacOS`. Initialize data
directories before token/config writes. Preserve the Windows legacy `.env`
fallback; the Mac app must not depend on one beside the bundled executable.
Do not package developer credentials or caches.

Keep read-only resources separate: `.ico` on Windows, `.icns` for the Mac
bundle, and PNG for Qt runtime use. Provide a legible menu-bar asset in both
light/dark appearances. Test paths with spaces, Unicode, unrelated working
directories, and a read-only bundle using injected platform/home resolvers.
Provide bounded logs under `~/Library/Logs/Lyricfy` for Finder/login failures,
without tokens, secrets, or full playback payloads.

### Autostart

Preserve the current `AUTOSTART_ENABLED` and `AUTOSTART_START_HIDDEN`
configuration keys and tray/settings controls.

- Windows: retain the per-user Run Registry implementation.
- macOS: create or remove a per-user LaunchAgent plist at
  `~/Library/LaunchAgents/com.lyricfy.overlay.plist`.

The initial Mac backend deliberately uses legacy plist registration to avoid a
new native bridge just for login setup. Apple recommends
[SMAppService for macOS 13+](https://developer.apple.com/documentation/servicemanagement/smappservice),
including effective authorization status. Keep the facade replaceable. If native
QA cannot establish reliable behavior with system login/background-item controls,
revisit this choice before release.

- Enable Mac autostart only for an installed bundle at a stable path. Disable
  it in source builds and DMG/translocated launches with a clear installation
  instruction; never register a temporary Python environment.
- Generate the plist with `plistlib` and atomic replacement. Use
  `Label=com.lyricfy.overlay`, `RunAtLoad=true`, and no `KeepAlive` restart loop.
  Follow Apple's [launchd job structure](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).
- Use a `ProgramArguments` array invoking Launch Services, for example
  `["/usr/bin/open", "-g", "-a", "/Applications/Lyricfy.app", "--args",
  "--start-hidden"]`. Derive the actual installed path; omit `--args` and
  `--start-hidden` for visible startup. Validate flags against `man open` on
  the target OS. Do not use a shell string or `-n` to force another instance.
- Enabling/updating takes effect at the next login; do not bootstrap another
  launch from the settings action. Disabling removes the plist and unloads
  any existing Lyricfy launcher job in the current user's session. Treat an
  already-absent job as success without hiding other errors or killing the GUI.
- Do not rewrite/re-enable the job on every app launch. Respect System Settings
  overrides. Report registration separately from effective approval: a plist's
  existence alone does not prove autostart is allowed. Explain repair if the
  installed app moves or is deleted.
- Return operation results to every caller. Do not show a successful toggle
  after a failed operation; retain/restore the previous state or clearly show
  failure. Other settings must still save. Test repeated enable/update/disable
  and rollback through both tray and Settings paths.

Validate login racing with manual launch and session restoration: require one
Mac app instance and one worker, adding a per-user instance guard if needed.
Reopening an existing instance must not overwrite its visibility. Document
disabling autostart before uninstall and retaining data unless explicitly removed.

### Overlay and Tray

PySide6 supports macOS. The shared Qt overlay uses `FramelessWindowHint` and
`WindowStaysOnTopHint`, which must be tested on macOS. The existing Win32/DWM
calls are optional enhancements and must remain guarded behind a Windows-only
platform check.

`QSystemTrayIcon` maps to the macOS menu bar. Preserve all existing tray menu
actions: show, hide, settings, snap home, playback mode, display presets,
overlay controls, startup choices, version, and exit.

Use `LSUIElement=true` for the packaged menu-bar utility; Apple's
[Launch Services keys](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/LaunchServicesKeys.html)
describe this behavior. Retain `setQuitOnLastWindowClosed(False)` and ensure
explicit Quit stops workers. If the tray is unavailable, keep the overlay
visible with a usable exit path. Review spontaneous hide/minimize restoration
so it does not fight macOS focus, Spaces, or Mission Control.

Confirm the following manually on macOS because Qt window-manager behavior
cannot be fully proven by unit tests:

- The overlay remains visible above Spotify and desktop windows.
- The overlay has no unwanted native title bar or border.
- Dragging, screen changes, partially off-screen positioning, and Snap Home
  behave as on Windows.
- Settings and combo-box popups remain usable while the overlay is topmost.
- The tray icon/menu works after closing and reopening the overlay.
- Retina/mixed-DPI monitors, monitor removal, and light/dark menu-bar appearance
  work without assuming pixel-identical rendering to Windows.

Use Qt/system fonts for Mac defaults, labels, and stylesheets. Retain Segoe UI
on Windows and honor saved fonts when installed; test fallback when a Windows
config references an unavailable font.

Keep current shortcut actions, but label Reload as `Command+R` on macOS.
Qt maps `ControlModifier` to Command and `MetaModifier` to physical Control on
Mac; adding Meta as a supposed Command fix would be incorrect. Use native
shortcut rendering where practical and update hardcoded help/reconnect strings.
See [Qt keyboard modifiers](https://doc.qt.io/qt-6/qt.html#KeyboardModifier-enum).
The existing `keyPressEvent` shortcuts are focused-window shortcuts, not global
hotkeys; hidden-overlay recovery continues through the menu bar.

## Implementation Phases

Tests accompany each phase; Phase 4 completes regression coverage rather than
postponing dependency installation and all testing until then.

### Phase 0: Native Feasibility and Early Bundle

1. Establish a Mac test machine and a Windows regression environment. Record
   Python, OS/architecture, Spotify version, and signing-credential availability.
2. Add Windows dependency markers early enough to install on Mac. Probe
   Spotify's actual dictionary and capture fixtures for units, metadata,
   identity, artwork, missing-track states, and scripting errors.
3. Build a minimal `.app` with identity/permission metadata; test Finder launch,
   prompt/denial/recovery, query latency, overlay/menu-bar behavior, and the
   proposed login launch method. Repeat with Developer ID/hardened runtime as
   soon as credentials exist.

Acceptance criteria: native evidence supports the scripting and bundle design
before the large Windows refactor. Record untested signing, minimum-OS, and
architecture combinations explicitly; failures here feed back into the plan.

### Phase 1: Cross-Platform Foundations

1. Create `platform` modules and move the current Windows playback and
   autostart behavior into their Windows implementations without changing its
   behavior.
2. Make the playback and autostart factories choose a backend from
   `sys.platform`.
3. Replace Windows-only identifiers in shared code with platform-neutral names
   where they describe generic non-API/local playback.
4. Update configuration defaults and validation so the default local backend is
   valid on both OSes, accepting legacy `windows` values as `local`.
5. Add native macOS packaged data-path resolution and platform-appropriate icon
   resolution.

Acceptance criteria:

- Windows starts and uses its current non-API media-session client exactly as
  before.
- API mode is still available on Windows and can be selected from Settings and
  the tray.
- Code import and configuration loading work on macOS without `winsdk`.
- Existing configuration round trips retain API selection and unrelated values.
- Pure Windows identity tests still run on Mac; WinRT tests skip before imports.

### Phase 2: macOS Non-API Playback

1. Implement `MacSpotifyClient` and the validated static script using `osascript`.
2. Return `TrackInfo` using a stable Spotify identifier when available. Use a
   deterministic fallback identifier specified above only when necessary.
3. Supply album artwork through `cover_url` so the shared cover-art repository
   downloads and caches it.
4. Translate expected scripting and process failures into actionable but safe
   user messages. Treat transient absence of playback as no current track.
5. Select the macOS local client when the user selects Non-API mode.
6. Integrate cancellation, stale-result protection, permission recovery, and
   hidden-startup deferral into `PlaybackWorker`/`AppController`.

Acceptance criteria:

- Playing, paused, and no-current-track states produce correct overlay state.
- Progress and duration keep synced `.lrc` lyrics aligned within the existing
  polling behavior. Target play/pause/seek updates within 2 seconds at the
  default poll interval on the reference Mac; record latency and lyric drift.
  Paused progress stays fixed and seeks re-anchor on the next valid snapshot.
- Album artwork works whenever Spotify supplies an artwork URL.
- The app explains how to grant Automation permission when macOS blocks Spotify
  scripting, and reconnect succeeds after permission is granted.
- Hide/reconnect/Quit remain responsive during script timeouts and pending
  prompts, without duplicate workers, orphan processes, or stale updates.

### Phase 3: macOS Autostart and UI Labels

1. Implement LaunchAgent creation, replacement, and removal safely using
   `plistlib` rather than handwritten XML.
2. Make UI and tray text platform-neutral, such as `Auto start on login`, while
   keeping Windows behavior intact.
3. Ensure a hidden autostart opens only the tray/menu-bar application and can be
   restored through its Show action.
4. Complete operation-result handling, installed-app checks, fonts/shortcuts,
   duplicate-launch behavior, and System Settings override handling.

Acceptance criteria:

- Enabling and disabling autostart changes only Lyricfy's LaunchAgent.
- Enabling `Start Hidden` persists the argument in the LaunchAgent.
- A sign-out/sign-in test launches the packaged app exactly once.
- Hidden startup produces no Spotify launch, polling, or authorization UI.
- Quit stays quit; failures do not leave a falsely successful startup toggle.

### Phase 4: Dependencies, Tests, and Regression Coverage

1. Complete dependency verification using `sys_platform == "win32"` markers
   for `winsdk`, `pefile`, and `pywin32-ctypes`, retaining
   `python -m pip install -r requirements.txt` on both platforms. Verify the
   full pinned dependency set resolves, not just the three marked packages.
2. Remove unconditional Windows package imports from cross-platform tests.
3. Keep native Windows media-session tests Windows-only and pure helpers portable.
4. Add mocked unit tests for the macOS scripting command, output parser,
   error cases, timeouts, track identity, artwork URL, and paused/playing state.
5. Add config-migration, factory/import-isolation, API error/cooldown,
   data/resource-path, autostart lifecycle/failure, and worker cancellation/
   stale-event/hidden-startup tests. Mock native writes and subprocesses.
6. Add Windows/macOS CI with explicit runner OS/architecture and Python versions.
   Run `python -m pip check`, `python -m pytest`, and native builds. Use
   `QT_QPA_PLATFORM=offscreen` for tests that do not need the window manager.
   Real Spotify, TCC consent, and login checks require separate interactive QA.

Acceptance criteria:

- `pip install -r requirements.txt` works on supported Windows and macOS
  environments.
- `pytest` passes on both OSes. Skip foreign-platform native tests before their
  imports; a missing required native dependency fails its own OS's CI job
  rather than silently skipping coverage.
- Windows-specific test coverage is retained rather than removed.
- Unit tests do not modify the real Registry, LaunchAgents, or user configuration.

### Phase 5: macOS Packaging and Distribution

1. Track `Lyricfy-macos.spec`, `build-macos.sh`, the scripting resource, and an
   entitlements plist. A fresh clone must contain every build input without
   depending on ignored Windows build artifacts.
2. Convert the existing source artwork into a production `.icns` file with all
   required icon sizes and include it in `Lyricfy.app`.
3. Use an `onedir`, windowed `.app` with `argv_emulation=False`, explicit
   identifier/version/minimum OS, and required Qt Cocoa/image plugins.
   PyInstaller discourages macOS
   [onefile bundles](https://pyinstaller.org/en/v6.19.0/usage.html#building-macos-app-bundles)
   and [argv emulation with GUI toolkits](https://pyinstaller.org/en/v6.19.0/feature-notes.html#optional-argv-emulation).
4. Build on macOS for each advertised architecture, not by cross-compiling from
   Windows. Validate Python and all native binaries; a universal PySide wheel
   alone is insufficient. See [PyInstaller architecture support](https://pyinstaller.org/en/v6.19.0/feature-notes.html#macos-multi-arch-support).
5. Produce preview ZIPs preserving symlinks/permissions and a production DMG.
   Test the extracted/installed artifact without Python, the source checkout,
   or developer shell variables, not just the app in the build directory.
6. Sign the app and nested binaries with Developer ID Application, hardened
   runtime, required entitlements, and a secure timestamp. Verify signatures;
   keep certificates and notarization credentials outside the repository.
7. Submit with `xcrun notarytool`, require an accepted result, and staple/validate
   the ticket. For ZIP distribution, staple the app before recreating the ZIP;
   notarize/staple the final DMG as well when distributing it. Follow Apple's
   [notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow).
8. Run signature, `spctl`, and stapler checks plus a clean-account Finder test
   of a downloaded quarantined artifact, including offline launch after
   download/installation.

Acceptance criteria:

- Double-clicking `Lyricfy.app` launches correctly on the supported macOS
  architecture.
- The signed/notarized production DMG opens without Gatekeeper workaround.
- The app has the intended name, icon, bundle identifier, and user-data path.
- Automation works with the production signature. Without signing credentials,
  only the development/preview milestone can complete; signing/notarization
  is a public-release gate, not an optional production follow-up.

### Phase 6: Documentation and Manual QA

1. Update `README.md` with platform-specific install, run, configuration, and
   build instructions.
2. Document macOS Automation permission behavior for Spotify.
3. Explain Mac distribution requirements: Apple Developer signing and
   notarization for releases outside the App Store.
4. Add a macOS QA checklist covering playback, lyrics, API mode, cover art,
   settings persistence, tray, shortcuts, multi-monitor drag behavior, autostart,
   build, and uninstall/data retention.
5. Document batch downloading as a source CLI requiring Python/API credentials.
   Its default lyrics/report paths point to the repository in source mode.
   Document copying downloaded `.lrc` files into the packaged app's lyric
   directory; a configurable CLI output directory would be a separate change.
6. Verify browser OAuth from the windowed app with the loopback redirect, token
   persistence, cancellation, and an occupied callback port. Supported GUI
   flows must not depend on typing a callback URL into an invisible terminal.

Acceptance criteria: README support claims match tested release artifacts.
Record OS, architecture, Spotify version, artifact version, and results; keep
untested combinations and native limitations explicit.

## Automated Test Matrix

| Area | Windows | macOS |
| --- | --- | --- |
| Config migration, normalization, save/load | Required | Required |
| Platform factory and import isolation | Mock all OS choices | Mock all OS choices |
| Lyrics, LRCLIB cache, sync engine | Required | Required |
| Overlay layout, drag, font fallback | Required | Required |
| Spotify API client/errors/cooldown | Mocked; no credentials | Mocked; no credentials |
| Windows identity helpers | Required | Required |
| Native Windows media session | Required native dependency | Skip before WinRT imports |
| macOS scripting parser/client failures | Mocked | Mocked |
| Worker cancellation, stale events, hidden startup | Required | Required |
| Data/resource paths | Mock both OSes and frozen/source modes | Mock both OSes and frozen/source modes |
| Registry autostart lifecycle/results | Mocked | Mocked |
| LaunchAgent lifecycle/results | Mocked paths/processes | Mocked paths/processes |
| PyInstaller app bundle | Windows executable build | macOS `.app` build |

Use recorded/synthetic snapshots for Unicode/escaping, malformed output, units,
unknown duration, identity stability, missing artwork, denied access, and
timeouts. Inject command runners, clocks, and path resolvers where needed.
Offscreen tests establish logic, not native window ordering, consent, or login
behavior; the latter require the checklist below for each advertised target.

## Manual macOS QA Checklist

- Launch the packaged `.app` on a clean user account.
- Verify the downloaded, quarantined artifact without Python; verify offline
  launch after notarization/stapling and the minimum supported OS/architecture.
- Confirm the application icon, menu-bar icon, and application name.
- Select Non-API mode and approve the Spotify Automation prompt.
- Deny access, re-enable it in System Settings, and reconnect. Repeat from Finder,
  login startup, and after a signed app update, not only from Terminal.
- Verify title, artist, album art, playing/paused state, duration, and lyric
  synchronization for multiple songs.
- Verify repeat, seeks in both directions, pause/resume, unknown duration,
  sleep/wake, missing metadata, advertisements, podcasts, and local files.
- Verify local `.lrc`, LRCLIB fallback, auto-saved lyrics, clearing downloaded
  cache, and batch lyric download.
- Verify Spotify API playback, expired/saved tokens, canceled browser login,
  occupied callback port, denied API access, and rate-limit recovery.
- Verify every display preset, setting, color, font, cover mode, drag behavior,
  partial edge positioning, Snap Home, hide/show, and shortcuts.
- Verify Retina/mixed-DPI displays, monitor removal, light/dark menu bar,
  focused-window shortcut behavior, fullscreen Spaces, Mission Control, and
  Stage Manager. Record limitations without promising universal topmost behavior.
- Verify system login autostart for both visible and hidden startup choices.
- Verify no polling/prompts while hidden, no-tray recovery, duplicate launches,
  System Settings overrides, app relocation, update, Quit without relaunch, and
  disabling autostart before uninstall. Data survives bundle replacement.
- Hide/reconnect/Quit during a script or permission wait; check for orphan
  processes, duplicate workers, and stale lyric updates.
- Verify behavior with Spotify absent, stopped, permission denied, network
  unavailable, and invalid API credentials.

## Known macOS Constraints

- Spotify scripting can change or be blocked by Automation permissions. Record
  tested Spotify versions. API mode is an explicit alternative subject to its
  own credentials, access, network, and quota requirements.
- A floating overlay cannot be guaranteed to appear above every macOS system UI
  surface, such as secure dialogs, fullscreen Spaces, or Mission Control.
- Building and signing a distributable `.app` requires a macOS build machine.
- The planned Developer ID-signed/notarized public release needs Apple Developer
  credentials; local preview builds are a separate milestone.
- Windows tests cannot establish native macOS compatibility. Publish only the
  OS/architecture combinations that passed native bundle QA.

## Out of Scope for Initial Port

- A Swift or SwiftUI rewrite.
- Mac App Store sandboxing and distribution.
- Linux support, unless platform abstractions make it straightforward later.
- Replacing Spotify API authentication or redesigning the overlay UI.
- Global hotkeys, playback-control features, guaranteed podcast lyrics, and a
  new batch-download GUI.
