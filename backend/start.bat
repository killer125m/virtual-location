@echo off
cd /d %~dp0
echo Checking dependencies...
if not exist node_modules (
  echo First run, installing packages, please wait 1-2 minutes...
  call npm install
  if errorlevel 1 (
    echo Install failed. Check network and try again.
    pause
    exit /b 1
  )
)
echo Starting backend, open http://localhost:3000
call npm start
pause
