@echo off
setlocal
set VERSION=v1.6.3

echo ========================================
echo Building Lyricfy %VERSION%....
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

.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'src'); from lyric_overlay.update_key import PUBLIC_KEY_HEX; sys.exit(0 if len(PUBLIC_KEY_HEX) == 64 and all(c in '0123456789abcdef' for c in PUBLIC_KEY_HEX) else 1)"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Configure the release public key before building. See RELEASE_GUIDE.md.
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building executable...
echo.

.venv\Scripts\pyinstaller.exe --noconfirm --clean Lyricfy.spec

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
