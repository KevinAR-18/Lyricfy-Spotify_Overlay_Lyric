@echo off
setlocal
set VERSION=v1.3.0

echo ========================================
echo Building Lyricfy %VERSION%...
echo ========================================
echo.

if not exist .venv\Scripts\pyinstaller.exe (
    echo ERROR: PyInstaller is not installed in .venv
    echo Run:
    echo   .venv\Scripts\python.exe -m pip install pyinstaller
    echo.
    pause
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building executable...
echo.

.venv\Scripts\pyinstaller.exe ^
  --name "Lyricfy" ^
  --onefile ^
  --windowed ^
  --icon=icon.ico ^
  --add-data "icon.ico;." ^
  --hidden-import=PySide6.QtCore ^
  --hidden-import=PySide6.QtGui ^
  --hidden-import=PySide6.QtWidgets ^
  --hidden-import=spotipy ^
  --hidden-import=spotipy.oauth2 ^
  --hidden-import=winsdk.windows.media.control ^
  --hidden-import=requests ^
  --hidden-import=dotenv ^
  --exclude-module=PyQt5 ^
  --exclude-module=PyQt6 ^
  --exclude-module=PySide2 ^
  --exclude-module=redis ^
  --exclude-module=winrt ^
  --exclude-module=PySide6.QtMultimedia ^
  --exclude-module=PySide6.QtDesigner ^
  --exclude-module=PySide6.QtHelp ^
  --exclude-module=PySide6.QtTest ^
  --exclude-module=PySide6.QtQuick ^
  --exclude-module=PySide6.QtQml ^
  --exclude-module=PySide6.QtWebEngineCore ^
  --exclude-module=PySide6.QtWebEngineQuick ^
  --exclude-module=PySide6.QtWebEngineWidgets ^
  src\main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo ERROR: Build failed
    echo ========================================
    pause
    exit /b 1
)

echo Copying icon.ico to dist...
copy /y icon.ico dist\icon.ico >nul

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo ERROR: Failed to copy icon.ico to dist
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete: Lyricfy %VERSION%
echo Output: dist\Lyricfy.exe
echo Icon: dist\icon.ico
echo ========================================
echo.
echo Runtime data location after build:
echo   %%APPDATA%%\Lyricfy\
echo.
echo Files created there on first run:
echo   .env
echo   .spotify_cache
echo   assets\lrc\
echo.
pause
