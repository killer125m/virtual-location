@echo off
cd /d %~dp0
echo Starting virtual location with Docker...
docker compose up -d --build
if errorlevel 1 (
  echo Start failed. Make sure Docker Desktop is running.
  pause
  exit /b 1
)
echo Started. Open http://localhost:3000
echo It will auto-restart after reboot as long as Docker Desktop starts on boot.
start http://localhost:3000
pause
