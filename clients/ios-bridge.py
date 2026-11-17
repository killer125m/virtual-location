#!/usr/bin/env python3
"""iOS 橋接程式原型 (無越獄)
電腦監聽後端 WebSocket，收到座標就用 pymobiledevice3 寫入 iPhone。
需求: pip install pymobiledevice3 python-socketio
     iPhone 信任電腦、開開發者模式、USB 或 Wi-Fi 連線
用法: BACKEND=http://localhost:3000 python3 ios-bridge.py
"""
import os, subprocess, sys
import socketio

BACKEND = os.environ.get("BACKEND", "http://localhost:3000")
DEVICE_ID = os.environ.get("DEVICE_ID", "ios-bridge-01")

def set_location(lat, lng):
    cmd = ["pymobiledevice3", "developer", "dvt", "simulate-location", "set", "--", str(lat), str(lng)]
    print("執行:", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout or r.stderr)

def clear_location():
    subprocess.run(["pymobiledevice3", "developer", "dvt", "simulate-location", "clear"])

sio = socketio.Client()
@sio.event
def connect():
    print("已連上後端", BACKEND)
    sio.emit("register", {"id": DEVICE_ID, "type": "ios-bridge", "name": "iPhone 橋接"})
@sio.on("location:update")
def on_loc(data):
    if data.get("deviceId") == DEVICE_ID:
        loc = data["location"]
        set_location(loc["lat"], loc["lng"])
@sio.on("location:clear")
def on_clear(data):
    if data.get("deviceId") == DEVICE_ID:
        clear_location()

if __name__ == "__main__":
    try:
        sio.connect(BACKEND)
        sio.wait()
    except KeyboardInterrupt:
        sys.exit(0)
