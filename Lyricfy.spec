# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.'), ('src\\lyric_overlay\\cinematic\\Cinematic.qml', 'lyric_overlay\\cinematic')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'spotipy', 'spotipy.oauth2', 'winsdk.windows.media.control', 'winsdk.windows.storage.streams', 'requests', 'dotenv'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'redis', 'winrt', 'PySide6.QtMultimedia', 'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtTest', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets'],
    noarchive=False,
    optimize=0,
)

# Strip out heavy, unused Qt modules pulled in by PySide6 QML hooks
UNWANTED_QT_MODULES = {
    'webengine',
    'quick3d',
    'qt3d',
    'charts',
    'graphs',
    'datavisualization',
    'location',
    'positioning',
    'sensors',
    'multimedia',
    'spatialaudio',
    'texttospeech',
    'virtualkeyboard',
    'qtvkb',
    'pdf',
    'scxml',
    'remoteobjects',
    'websockets',
    'webview',
}

def is_unwanted(path):
    lower = path.lower()
    return any(mod in lower for mod in UNWANTED_QT_MODULES)

a.binaries = [b for b in a.binaries if not is_unwanted(b[0])]
a.datas = [d for d in a.datas if not is_unwanted(d[0])]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Lyricfy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
