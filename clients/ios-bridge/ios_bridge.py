#!/usr/bin/env python3
"""iPhone 橋接程式 (無越獄, Windows 用)
原理: iPhone 本身不准 App 改系統 GPS, 所以由這台 Windows 電腦當橋接。
電腦監聽中控後端 (Socket.io), 收到座標就用 pymobiledevice3
透過 USB 寫入 iPhone。

關鍵: pymobiledevice3 的 `developer dvt simulate-location set`
會一直佔住連線、直到被中斷才結束 (官方文件: "keeping the session
open until interrupted"), 所以不能用 subprocess.run() 等它跑完,
否則會卡 90 秒、逾時被砍掉、定位跟著還原, 路線播放也永遠跑不起來。
正確做法: 用 Popen 在背景跑著, 要換位置就先砍掉舊的、再開新的;
要還原就砍掉它 (再補一次 clear)。

iOS 17+ 用 dvt 版 (RSD tunnel 會自動建, 不用另外跑 tunneld)。
iOS 16 以下 dvt 會失敗, 自動改用舊版 `developer simulate-location set`
(那個跑完就回傳、定位一直留著, 直到 clear)。

用法:
  1. 先裝 Python 3.11+ (安裝時勾 Add to PATH) + iTunes (Apple 官網版, 裝驅動用)
  2. 雙擊 install.bat
  3. iPhone 用 USB 接電腦, 點「信任此電腦」, 開開發者模式:
     設定 > 隱私權與安全性 > 開發者模式 > 開啟, 重開機
  4. 雙擊 start.bat (或: python ios_bridge.py)
  5. 到 http://localhost:3000, 選 ios-bridge-01 這台裝置, 瞬移 / 播路線

測試 (不連後端, 直接改一次定位, 按 Ctrl+C 停止並還原):
  python ios_bridge.py --test 25.0339 121.5645
  python ios_bridge.py --clear
  python ios_bridge.py --list

環境變數:
  BACKEND_URL  後端位址, 預設 http://localhost:3000
  DEVICE_ID    裝置 ID, 預設 ios-bridge-01
  DEVICE_NAME  裝置名稱, 預設 iPhone 橋接
"""
import argparse
import os
import subprocess
import sys
import threading
import time

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:3000")
# 打包成 .exe 時預設連雲端, 不用再設 BACKEND_URL; 本機跑 .py 時預設還是 localhost
if getattr(sys, "frozen", False) and "BACKEND_URL" not in os.environ:
    BACKEND_URL = "https://virtual-location.onrender.com"
DEVICE_ID = os.environ.get("DEVICE_ID", "ios-bridge-01")
DEVICE_NAME = os.environ.get("DEVICE_NAME", "iPhone 橋接")
DEVICE_UDID = os.environ.get("DEVICE_UDID", "")


def _pmd3_cmd():
    """pymobiledevice3 指令: 打包成 .exe 時用同目錄的 pymobiledevice3.exe,
    沒打包時用 PATH 上的 pymobiledevice3。"""
    if getattr(sys, "frozen", False):
        bundled = os.path.join(os.path.dirname(sys.executable), "pymobiledevice3.exe")
        if os.path.exists(bundled):
            return [bundled]
    return ["pymobiledevice3"]


def _find_remote_udid():
    """找 Wi-Fi 上的 iPhone: 第一次 USB 配對後, 同 Wi-Fi 下 remote list 會看到它。
    回傳 UDID (40 碼 hex) 或空字串。"""
    import re
    for args in (["remote", "list"], ["usbmux", "list"]):
        ok, out = run(_pmd3_cmd() + args, timeout=30)
        if ok and out:
            m = re.findall(r"\b[0-9a-fA-F]{40}\b", out)
            if m:
                return m[0]
    return ""

# 正在背景跑的 dvt simulate-location set 程序 (iOS 17+ 用)。定位要一直留著,
# 這個程序就不能停; 換位置 / 還原時先砍掉它。
_sim_proc = None
_sim_mode = None  # 'dvt' 或 'legacy'


def run(cmd, timeout=60):
    """跑一個「會自己結束」的指令, 回傳 (成功, 輸出)。"""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out.strip()
    except FileNotFoundError:
        return False, "找不到 pymobiledevice3, 請先跑 install.bat"
    except subprocess.TimeoutExpired:
        return False, "指令逾時, 請檢查 iPhone 是否還連著 USB"


def list_devices():
    ok, out = run(_pmd3_cmd() + ["usbmux", "list"])
    print(out or "沒有看到裝置")
    return ok


def _stop_sim():
    """停掉背景的定位模擬 (砍掉 dvt 程序; 舊版模式則跑一次 clear)。"""
    global _sim_proc, _sim_mode
    proc, mode = _sim_proc, _sim_mode
    _sim_proc, _sim_mode = None, None
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    if mode == "legacy":
        run(_pmd3_cmd() + ["developer", "simulate-location", "clear"], timeout=30)


def _drain_stream(stream, prefix):
    """背景把子程序的 stderr 一行行印到橋接視窗, 這樣它真正的錯誤才看得到。
    不這樣做: stderr 沒人讀, 寫滿緩衝區會卡住程序, 橋接還會誤判成功。"""
    try:
        for line in stream:
            line = line.rstrip()
            if line:
                print(f"{prefix} {line}", flush=True)
    except Exception:
        pass


def _start_dvt(lat, lng, grace=8):
    """背景啟動 dvt simulate-location set。
    幾秒內就自己結束 = 報錯 (回傳錯誤訊息); 還在跑 = 定位已寫入。"""
    try:
        proc = subprocess.Popen(
            (_pmd3_cmd() + ["developer", "dvt", "simulate-location", "set"] + (["--udid", DEVICE_UDID] if DEVICE_UDID else []) + ["--", str(lat), str(lng)]),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        return None, "找不到 pymobiledevice3, 請先跑 install.bat"
    except Exception as e:
        return None, str(e)
    threading.Thread(target=_drain_stream, args=(proc.stderr, "[dvt]"), daemon=True).start()
    try:
        rc = proc.wait(timeout=grace)
        time.sleep(0.5)  # 等 drain thread 把最後的錯誤行印完
        return None, f"dvt simulate-location 結束, 結束碼 {rc} (原因看上面 [dvt] 的行)"
    except subprocess.TimeoutExpired:
        return proc, None  # 還在跑, 就是成功


_warned_proc = None


def _watch_sim():
    """背景監看模擬程序: 它中途結束 = 定位已還原, 馬上在視窗警告,
    不然橋接會一直以為定位還在, 手機卻早已跳回真實位置。"""
    global _warned_proc
    while True:
        time.sleep(5)
        proc = _sim_proc
        if proc is not None and proc.poll() is not None and proc is not _warned_proc:
            _warned_proc = proc
            print(f"[橋接] 注意: 模擬程序已結束 (結束碼 {proc.returncode}), iPhone 定位可能已還原, 請到中控台再瞬移一次", flush=True)


def set_location(lat, lng):
    global _sim_proc, _sim_mode
    print(f"[橋接] 寫入 iPhone: {lat}, {lng}", flush=True)
    _stop_sim()  # 先停掉上一個位置的模擬, 再開新的
    proc, err = _start_dvt(lat, lng)
    if proc is not None:
        _sim_proc, _sim_mode = proc, "dvt"
        print("[橋接] 成功, iPhone 現在就是這個位置 (模擬程序在背景跑著, 不要關這個視窗)", flush=True)
        return True
    # USB 沒找到, 試 Wi-Fi: 第一次 USB 配對後, 同 Wi-Fi 下 remote list 找得到 UDID
    if not DEVICE_UDID:
        remote = _find_remote_udid()
        if remote:
            print(f"[橋接] USB 沒找到, 改試 Wi-Fi 上的 iPhone ({remote[:8]}...)", flush=True)
            globals()["DEVICE_UDID"] = remote
            proc, err = _start_dvt(lat, lng)
            if proc is not None:
                _sim_proc, _sim_mode = proc, "dvt"
                print("[橋接] 成功 (Wi-Fi), iPhone 現在就是這個位置", flush=True)
                return True
    # dvt 不行 (通常是 iOS 16 以下), 改用舊版指令: 跑完就回傳、定位留著
    print(f"[橋接] dvt 模式不行 ({err}), 改試 iOS 16 以下用的舊版指令...", flush=True)
    ok, out = run(_pmd3_cmd() + ["developer", "simulate-location", "set"] + (["--udid", DEVICE_UDID] if DEVICE_UDID else []) + ["--", str(lat), str(lng)], timeout=60)
    if ok:
        _sim_mode = "legacy"
        print("[橋接] 成功 (舊版模式), iPhone 現在就是這個位置", flush=True)
        return True
    print("[橋接] 失敗:", flush=True)
    print(out or err, flush=True)
    print("常見原因: 沒信任電腦 / 沒開開發者模式 / USB 鬆了 / iOS 剛升級要等 pymobiledevice3 更新", flush=True)
    return False


def clear_location():
    print("[橋接] 還原 iPhone 真實定位", flush=True)
    _stop_sim()  # 砍掉背景模擬程序, 定位就跟著還原
    # 再補一次 clear 指令, 清掉舊版模式可能留下的模擬 (失敗也沒關係)
    run(_pmd3_cmd() + ["developer", "dvt", "simulate-location", "clear"], timeout=30)
    run(_pmd3_cmd() + ["developer", "simulate-location", "clear"], timeout=30)
    print("[橋接] 已還原", flush=True)
    return True


def serve():
    try:
        import socketio
    except ImportError:
        print("缺少 python-socketio, 請先跑 install.bat (pip install -r requirements.txt)")
        sys.exit(1)

    sio = socketio.Client(reconnection=True, reconnection_attempts=0)

    @sio.event
    def connect():
        print(f"[橋接] 已連上後端 {BACKEND_URL}", flush=True)
        sio.emit("register", {"id": DEVICE_ID, "type": "ios-bridge", "name": DEVICE_NAME})

    @sio.event
    def disconnect():
        print("[橋接] 與後端斷線, 自動重連中...", flush=True)

    @sio.on("location:update")
    def on_loc(data):
        if not isinstance(data, dict):
            return
        if data.get("deviceId") != DEVICE_ID:
            return
        loc = data.get("location") or {}
        try:
            set_location(float(loc["lat"]), float(loc["lng"]))
        except (KeyError, TypeError, ValueError):
            print("[橋接] 收到不完整的座標, 已忽略:", data, flush=True)

    @sio.on("location:clear")
    def on_clear(data):
        if isinstance(data, dict) and data.get("deviceId") == DEVICE_ID:
            clear_location()

    print(f"[橋接] 啟動, 裝置 {DEVICE_ID} ({DEVICE_NAME}), 後端 {BACKEND_URL}")
    print("[橋接] 請確認 iPhone 已用 USB 接上並信任電腦, 然後到中控台選這台裝置")
    threading.Thread(target=_watch_sim, daemon=True).start()
    try:
        while True:
            try:
                sio.connect(BACKEND_URL)
                sio.wait()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[橋接] 連線失敗, 5 秒後重試: {e}", flush=True)
                time.sleep(5)
    except KeyboardInterrupt:
        print("\n[橋接] 已停止, 還原 iPhone 真實定位...", flush=True)
        clear_location()


def main():
    p = argparse.ArgumentParser(description="iPhone 橋接程式")
    p.add_argument("--test", nargs=2, type=float, metavar=("LAT", "LNG"), help="直接改一次定位, 例: --test 25.0339 121.5645 (按 Ctrl+C 停止並還原)")
    p.add_argument("--clear", action="store_true", help="還原真實定位")
    p.add_argument("--list", action="store_true", help="列出 USB 連上的 iPhone")
    args = p.parse_args()
    if args.list:
        sys.exit(0 if list_devices() else 1)
    if args.clear:
        sys.exit(0 if clear_location() else 1)
    if args.test:
        if not set_location(args.test[0], args.test[1]):
            sys.exit(1)
        print("[橋接] 現在打開 iPhone 地圖 App, 位置應該就是上面那組座標。", flush=True)
        print("[橋接] 這個視窗不要關, 關掉定位就還原。按 Ctrl+C 停止並還原。", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[橋接] 停止測試, 還原中...", flush=True)
            clear_location()
            sys.exit(0)
    serve()


if __name__ == "__main__":
    main()
