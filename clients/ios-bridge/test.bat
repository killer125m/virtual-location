@echo off
cd /d %~dp0
echo Testing iPhone connection...
echo 1. List USB devices:
python ios_bridge.py --list
echo.
echo 2. Try moving iPhone to Taipei 101 (25.0339, 121.5645):
python ios_bridge.py --test 25.0339 121.5645
echo.
echo If it works, open iPhone Maps app, your location should be at Taipei 101.
echo To restore: python ios_bridge.py --clear
pause
