@echo off
setlocal
set VERSION=v1.4.2

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


echo Building executable...
echo.

.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean packaging\windows.spec

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
