@echo off
echo ========================================
echo Building EcoLab Dashboard...
echo ========================================
echo.

REM Clean old build
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Cleaning old build files... done
echo.
echo NOTE: main and ui_theme_helper removed from hidden-import
echo       (now imported at top of launcher.py for PyInstaller compatibility)
echo.

echo Building PyInstaller...
echo.

.venv\Scripts\pyinstaller ^
  --name "EcoLab Dashboard" ^
  --onefile ^
  --windowed ^
  --icon=icon\logoecolab.ico ^
  --add-data "images;images" ^
  --add-data "icon;icon" ^
  --hidden-import=PySide6.QtCore ^
  --hidden-import=PySide6.QtGui ^
  --hidden-import=PySide6.QtWidgets ^
  --hidden-import=pyrebase ^
  --hidden-import=requests ^
  --hidden-import=google.oauth2.service_account ^
  --hidden-import=google_auth_oauthlib.flow ^
  --hidden-import=google.auth.transport.requests ^
  --hidden-import=loginmain ^
  --hidden-import=admin_window ^
  --hidden-import=session_manager ^
  --hidden-import=auth_service ^
  --hidden-import=firebase_settings ^
  --hidden-import=ui_theme_helper ^
  --hidden-import=lamp_setup ^
  --hidden-import=switch_setup ^
  --hidden-import=ac_setup ^
  --hidden-import=arrow_setup ^
  --hidden-import=smartsocket_popup ^
  --hidden-import=smartsocket_setup ^
  --hidden-import=ui_loginpage ^
  --hidden-import=ui_mainwindow ^
  --hidden-import=ui_functions ^
  --hidden-import=ui_role_selection ^
  --hidden-import=widgets.lamp_button ^
  --hidden-import=backend.growatt_backend ^
  --hidden-import=backend.weathercloud_backend ^
  --hidden-import=backend.mqtt_client ^
  --hidden-import=backend.mqtt_dht22_backend ^
  --hidden-import=backend.lampbutton_backend ^
  --hidden-import=backend.acbutton_backend ^
  --hidden-import=backend.growatt_worker ^
  --hidden-import=backend.mcu_status_backend ^
  --hidden-import=backend.smartsocket_backend ^
  --collect-all=pyrebase ^
  --collect-all=google ^
  launcher.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo ERROR: PyInstaller build failed!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo PyInstaller build complete!
echo Output: dist\EcoLabDashboard.exe
echo ========================================
echo.
echo Next steps:
echo 1. Copy credentials folder to dist\
echo 2. Test the exe
echo ========================================
pause
