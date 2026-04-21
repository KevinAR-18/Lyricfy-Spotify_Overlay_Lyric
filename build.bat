@echo off
setlocal

echo ========================================
echo Building Lyricfy...
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
  --hidden-import=requests ^
  --hidden-import=dotenv ^
  --collect-all=spotipy ^
  --collect-all=PySide6 ^
  src\main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo ERROR: Build failed
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete
echo Output: dist\Lyricfy.exe
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
