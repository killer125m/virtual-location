@echo off
cd /d %~dp0
echo Starting iPhone bridge...
echo Backend default http://localhost:3000
echo Keep this window open. Closing it stops the bridge.
python ios_bridge.py
pause
