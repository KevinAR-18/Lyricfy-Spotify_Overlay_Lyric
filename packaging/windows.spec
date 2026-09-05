# Build from a fresh clone: python -m PyInstaller packaging/windows.spec
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / "src" / "main.py")], pathex=[str(root / "src")],
    datas=[(str(root / "icon.ico"), ".")],
    hiddenimports=["winsdk.windows.media.control", "winsdk.windows.storage.streams", "spotipy.oauth2"],
    excludes=["PyQt5", "PyQt6", "PySide2", "redis", "winrt",
              "lyric_overlay.platform.playback_macos", "lyric_overlay.platform.autostart_macos",
              "PySide6.QtMultimedia", "PySide6.QtDesigner", "PySide6.QtHelp",
              "PySide6.QtTest", "PySide6.QtQuick", "PySide6.QtQml",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Lyricfy", console=False,
          icon=str(root / "icon.ico"), upx=False)
