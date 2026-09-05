# Run through build-macos.sh, which creates the ICNS from the tracked icon.png.
import os
import platform
import re
from pathlib import Path

root = Path(SPECPATH)
version = re.search(r'__version__ = "([^"]+)"',
                    (root / "src/lyric_overlay/__init__.py").read_text()).group(1)
identity = os.environ.get("LYRICFY_CODESIGN_IDENTITY") or None
architecture = os.environ.get("LYRICFY_TARGET_ARCH", platform.machine())
if architecture not in {"arm64", "x86_64"}:
    raise ValueError("Build a separate arm64 or x86_64 artifact with its native Python.")
a = Analysis(
    [str(root / "src/main.py")], pathex=[str(root / "src")],
    datas=[(str(root / "icon.png"), "."),
           (str(root / "assets/macos/tray.svg"), "assets/macos"),
           (str(root / "src/lyric_overlay/platform/spotify_snapshot.js"), "lyric_overlay/platform")],
    hiddenimports=["PySide6.QtSvg", "spotipy.oauth2"],
    excludes=["winsdk", "winreg", "PyQt5", "PyQt6", "PySide2", "redis",
              "lyric_overlay.platform.playback_windows", "lyric_overlay.platform.autostart_windows",
              "PySide6.QtMultimedia", "PySide6.QtDesigner", "PySide6.QtHelp",
              "PySide6.QtTest", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Lyricfy", console=False,
          argv_emulation=False, target_arch=architecture, codesign_identity=identity,
          entitlements_file=str(root / "packaging/macos-entitlements.plist") if identity else None)
coll = COLLECT(exe, a.binaries, a.datas, name="Lyricfy")
app = BUNDLE(
    coll, name="Lyricfy.app", icon=str(root / "build/macos-icons/Lyricfy.icns"),
    bundle_identifier="com.lyricfy.overlay",
    info_plist={
        "CFBundleName": "Lyricfy", "CFBundleDisplayName": "Lyricfy",
        "CFBundleShortVersionString": version, "CFBundleVersion": version,
        "LSMinimumSystemVersion": "13.0", "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "Lyricfy reads the current song and playback position from Spotify to display synchronized lyrics.",
    },
)
