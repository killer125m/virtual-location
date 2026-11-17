@echo off
cd /d %~dp0
echo Checking Python...
python --version
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ from python.org and tick Add to PATH.
  pause
  exit /b 1
)
echo Installing bridge packages, please wait 1-3 minutes...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Install failed. Check network and run install.bat again.
  pause
  exit /b 1
)
echo.
echo Install done. Next steps:
echo 1. Connect iPhone via USB and tap Trust This Computer
echo 2. On iPhone: Settings - Privacy and Security - Developer Mode - ON, then reboot
echo 3. Double-click start.bat
pause
