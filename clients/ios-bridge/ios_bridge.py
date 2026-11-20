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
路線播放時後端每秒推播一次, 但 dvt 模擬重開一次要 1-2 秒才生效,
每秒重開會讓手機定位在真實/模擬之間一直跳, 遊戲就不同步。
所以只移動超過 5 公尺才重開模擬, 且換位置時不再等 8 秒確認
(上一個模擬剛剛還在跑, 環境驗過是好的); 冷啟動才等 8 秒。
2026-11-20 修假「成功」: 手機沒被看到時直接報失敗不跑 dvt;
死了的模擬程序不再當成還在跑, grace=0 只給活著的程序。
同日修偵測: UDID 有兩種格式, 舊款 40 碼十六進位, 新款 (iPhone 12 之後)
是 8 碼-16 碼 (例 00008110-000C2A3B4D5E6F7A); 舊版正則只認 40 碼,
新手機永遠抓不到, 偏偏 iTunes 認得手機 (配對其實通了), 還讓 fail-fast
gate 誤判成手機沒接。偵測改用 `usbmux list --simple` (只問 usbmuxd
拿 UDID, 不連 lockdownd 配對), 兩種格式都認, 輸出不管結束碼。
同日修 Wi-Fi 偵測: `remote` 底下根本沒有 `list` 子命令 (11.57.0 的
remote 只有 tunneld/browse/rsd-info/start-tunnel/pair...), 舊版
`remote list` 只會印 "No such command 'list'", Wi-Fi 偵測從來沒成功過,
拔線就永遠找不回手機。改用 `usbmux list --network --simple`、
`remote browse` (wifi[].identifier) 與 `bonjour mobdev2` 找 Wi-Fi;
另修 set_location 的 Wi-Fi 重試是死碼 (拔過 USB 後 DEVICE_UDID 還留著
舊值, `if not DEVICE_UDID` 永遠不成立), 現改成 dvt 失敗就強制重找一次,
確認手機還在就再試一次。

iOS 17+ 用 dvt 版 (RSD tunnel 會自動建, 不用另外跑 tunneld)。
iOS 16 以下 dvt 會失敗, 自動改用舊版 `developer simulate-location set`
(那個跑完就回傳、定位一直留著, 直到 clear)。

用法:
  1. 先裝 Python 3.11+ (安裝時勾 Add to PATH) + iTunes (Apple 官網版, 裝驅動用)
  2. 雙擊 install.bat
  3. iPhone 用 USB 接電腦, 點「信任此電腦」, 開開發者模式:
     設定 > 隱私權與安全性 > 開發者模式 > 開啟, 重開機
  4. 雙擊 start.bat (或: python ios_bridge.py)
  5. 到 http://localhost:3000, 選你的 iPhone 橋接 (裝置 ID 會自動用手機 UDID 前 8 碼,
     例 ios-a1b2c3d4, 每支 iPhone 天生不一樣, 兩個人同時用也不會撞成同一台),
     瞬移 / 播路線

測試 (不連後端, 直接改一次定位, 按 Ctrl+C 停止並還原):
  python ios_bridge.py --test 25.0339 121.5645
  python ios_bridge.py --clear
  python ios_bridge.py --list

環境變數:
  BACKEND_URL  後端位址, 預設 http://localhost:3000
  DEVICE_ID    裝置 ID, 沒設時自動用手機 UDID 前 8 碼 (例 ios-a1b2c3d4), 找不到手機才用 ios-bridge-01
  DEVICE_NAME  裝置名稱, 預設 iPhone 橋接
"""
import argparse
import json
import os
import re
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
DEVICE_ID_FROM_ENV = "DEVICE_ID" in os.environ  # 有手動設 DEVICE_ID 就用手動的, 不自動改


def _pmd3_cmd():
    """pymobiledevice3 指令: 打包成 .exe 時用同目錄的 pymobiledevice3.exe,
    沒打包時用 PATH 上的 pymobiledevice3。"""
    if getattr(sys, "frozen", False):
        bundled = os.path.join(os.path.dirname(sys.executable), "pymobiledevice3.exe")
        if os.path.exists(bundled):
            return [bundled]
    return ["pymobiledevice3"]


# UDID 有兩種格式: 舊款 40 碼十六進位, 新款 (iPhone 12 之後) 是
# 8 碼-16 碼 (例 00008110-000C2A3B4D5E6F7A)。
_UDID_RE = re.compile(r"\b(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{8}-[0-9a-fA-F]{16})\b")


def _find_phone():
    """找 iPhone: 先查 USB (usbmux list), 再查 Wi-Fi。
    --simple 只問 usbmuxd 拿 UDID, 不連 lockdownd 配對, 最穩; 舊版
    pymobiledevice3 沒有 --simple 時再退回一般 list。輸出不管結束碼,
    只要印得出 UDID 就算找到 (list 印得出裝置卻回非零結束碼時也不能漏)。
    Wi-Fi 有三條路: usbmuxd 認得的 Wi-Fi 裝置 (`usbmux list --network
    --simple`)、Bonjour RSD/RemotePairing (`remote browse` 的 wifi 區,
    identifier 就是 UDID)、lockdown over Wi-Fi (`bonjour mobdev2`)。
    注意: 11.57.0 的 remote 底下根本沒有 `list` 這個子命令, 舊版
    `remote list` 只會印 "No such command 'list'", Wi-Fi 偵測從來沒成功過。
    回傳 (udid, 'USB'/'Wi-Fi') 或 ('', None)。"""
    for args, transport in (
        (["usbmux", "list", "--simple"], "USB"),
        (["usbmux", "list"], "USB"),
        (["usbmux", "list", "--network", "--simple"], "Wi-Fi"),
    ):
        _, out = run(_pmd3_cmd() + args, timeout=30)
        if out:
            m = _UDID_RE.findall(out)
            if m:
                return m[0], transport
    # Wi-Fi 經 Bonjour (iOS 17+ RSD/RemotePairing): `remote browse` 回傳
    # {"usb": [{"UniqueDeviceID": ...}], "wifi": [{"identifier": UDID, ...}]}。
    _, out = run(_pmd3_cmd() + ["remote", "browse", "--timeout", "5"], timeout=30)
    if out:
        try:
            data = json.loads(out)
        except Exception:
            data = None
        if isinstance(data, dict):
            for section, key, transport in (
                ("wifi", "identifier", "Wi-Fi"),
                ("usb", "UniqueDeviceID", "USB"),
            ):
                for entry in data.get(section) or []:
                    if isinstance(entry, dict):
                        v = entry.get(key) or ""
                        if _UDID_RE.fullmatch(v):
                            return v, transport
        m = _UDID_RE.findall(out)
        if m:
            return m[0], "Wi-Fi"
    # Wi-Fi 經 lockdown (mobdev2): 回傳 short_info 陣列, 內含 UniqueDeviceID。
    _, out = run(_pmd3_cmd() + ["bonjour", "mobdev2", "--timeout", "5"], timeout=30)
    if out:
        m = _UDID_RE.findall(out)
        if m:
            return m[0], "Wi-Fi"
    return "", None


def _find_remote_udid():
    """(相容舊呼叫) 找 Wi-Fi/USB 上的 iPhone UDID, 或空字串。"""
    udid, _ = _find_phone()
    return udid


_last_discovery = 0.0  # 上次 _refresh_phone 真正掃描的時間 (節流用)


def _refresh_phone(force=False):
    """重找一次 iPhone: 找到就 _apply_phone() 並回 True, 找不到回 False。
    預設 10 秒節流, 路線每秒推播時不會一直掃 Bonjour (remote browse /
    mobdev2 各要等幾秒); dvt 剛失敗時用 force=True 強制重掃一次。"""
    global _last_discovery
    now = time.time()
    if not force and now - _last_discovery < 10:
        return _phone_state == "connected"
    _last_discovery = now
    try:
        udid, transport = _find_phone()
    except Exception:
        return False
    if udid:
        _apply_phone(udid, transport)
        return True
    return False

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


_id_resolved = False
_phone_state = "unknown"  # 'connected' / 'missing' / 'unknown'
_phone_udid = ""
_sio = None  # serve() 裡的 Socket.io 客戶端, 給 _watch_phone 重新註冊用


def _apply_phone(udid, transport):
    """套用找到的 iPhone: 記下 UDID, 沒手動設 DEVICE_ID 時用 UDID 前 8 碼當裝置 ID,
    並在視窗印出連線狀態, 這樣才確認得了手機到底有沒有真的連上。"""
    global DEVICE_ID, DEVICE_NAME, DEVICE_UDID, _phone_udid, _phone_state
    DEVICE_UDID = udid
    _phone_udid = udid
    _phone_state = "connected"
    if not DEVICE_ID_FROM_ENV:
        # 新款 UDID 前面 00008110 是機型共用前綴, 每支都一樣, 不能當 ID;
        # 取連字號後面那段的前 8 碼。舊款 40 碼維持取前 8 碼。
        short = udid[9:17] if "-" in udid else udid[:8]
        DEVICE_ID = f"ios-{short.lower()}"
        DEVICE_NAME = f"iPhone 橋接 ({short})"
    print(f"[橋接] iPhone 已連上 ({transport}), 裝置 ID: {DEVICE_ID}", flush=True)


def _delete_device(device_id):
    """向後端刪掉舊的裝置紀錄 (換 ID 時用, 免得中控台留兩筆)。失敗也沒關係。"""
    try:
        import urllib.request
        req = urllib.request.Request(f"{BACKEND_URL}/api/devices/{device_id}", method="DELETE")
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception:
        pass


def _watch_phone():
    """背景每 15 秒檢查 iPhone 在不在: 啟動時沒接手機、之後才插上也會自動偵測到,
    不用重開橋接; 拔掉/斷線時在視窗警告, 這樣橋接視窗就能確認手機到底有沒有真的連上。"""
    global _phone_state
    while True:
        time.sleep(15)
        try:
            udid, transport = _find_phone()
        except Exception:
            continue
        if udid:
            if udid != _phone_udid:
                old_id = DEVICE_ID
                _apply_phone(udid, transport)
                if _sio is not None and getattr(_sio, "connected", False):
                    if DEVICE_ID != old_id:
                        _delete_device(old_id)
                    _sio.emit("register", {"id": DEVICE_ID, "type": "ios-bridge", "name": DEVICE_NAME})
            elif _phone_state != "connected":
                _phone_state = "connected"
                print(f"[橋接] iPhone 已連上 ({transport})", flush=True)
        else:
            if _phone_state == "connected":
                _phone_state = "missing"
                print("[橋接] iPhone 已斷開 (找不到裝置), 請檢查 USB 有沒有鬆、手機有沒有鎖屏、Wi-Fi 是不是同一個", flush=True)


def _ensure_device_id():
    """決定裝置 ID: 沒手動設 DEVICE_ID 時, 用 iPhone 的 UDID 前 8 碼當 ID
    (例 ios-a1b2c3d4), 每支 iPhone 天生不一樣, 兩個人同時用也不會撞成同一台。
    順便把 UDID 記下來, 後面 dvt 指令直接指這支手機。
    找不到手機時先用預設 ios-bridge-01, 之後 _watch_phone 會每 15 秒自動偵測,
    接上手機就自動換成手機 ID, 不用重開橋接。"""
    global DEVICE_ID, DEVICE_NAME, DEVICE_UDID, _id_resolved, _phone_state
    if _id_resolved or DEVICE_ID_FROM_ENV:
        return
    _id_resolved = True
    udid, transport = _find_phone()
    if udid:
        _apply_phone(udid, transport)
    else:
        _phone_state = "missing"
        print("[橋接] 找不到 iPhone, 先用 ios-bridge-01 (接上手機後會自動偵測, 不用重開橋接)", flush=True)


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


def _dist_m(a, b):
    """兩組座標的距離 (公尺, Haversine)。"""
    import math
    R = 6371000
    la1, lo1 = math.radians(a[0]), math.radians(a[1])
    la2, lo2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


_last_applied = None  # 上次真正寫入的座標 (lat, lng)
_last_restart = 0.0   # 上次重開模擬程序的時間


def _start_dvt(lat, lng, grace=8):
    """背景啟動 dvt simulate-location set。
    幾秒內就自己結束 = 報錯 (回傳錯誤訊息); 還在跑 = 定位已寫入。
    grace=0 時先等 1 秒再確認 (路線播放中換位置用, 環境剛剛才驗過是好的;
    程序若立刻崩潰, 1 秒內就會死, 就不會印假成功; 多等這 1 秒不影響路線)。
    stdin 用 PIPE (一直開著不關): 模擬開始後 pymobiledevice3 會停在
    "Press ENTER to exit>" 等人按 Enter 才結束, 定位就是靠這個程序活著
    才留得住。之前改成 DEVNULL 是錯的: 讀到 EOF 立刻結束, 寫入成功後
    程序馬上結束碼 0、定位跟著還原 (2026-11-20 11:24 就是這樣)。
    失敗的程序 (例如裝置已拔掉) 會自己結束碼 1, grace 檢查抓得到, 不靠 stdin。"""
    try:
        proc = subprocess.Popen(
            (_pmd3_cmd() + ["developer", "dvt", "simulate-location", "set"] + (["--udid", DEVICE_UDID] if DEVICE_UDID else []) + ["--", str(lat), str(lng)]),
            stdin=subprocess.PIPE,  # 一直開著不關: 模擬靠這個程序活著才留得住, 關掉 (DEVNULL) 會立刻結束、定位還原
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        return None, "找不到 pymobiledevice3, 請先跑 install.bat"
    except Exception as e:
        return None, str(e)
    threading.Thread(target=_drain_stream, args=(proc.stderr, "[dvt]"), daemon=True).start()
    if grace <= 0:
        # 剛啟動就崩的程序 (例如裝置已拔掉, usbmux 找不到 UDID) 1 秒內就會死,
        # 等一下再確認, 免得印假成功; 路線播放重開一次才多等 1 秒。
        time.sleep(1.0)
        if proc.poll() is not None:
            time.sleep(0.5)  # 等 drain thread 把最後的錯誤行印完
            return None, f"dvt simulate-location 結束, 結束碼 {proc.returncode} (原因看上面 [dvt] 的行)"
        return proc, None
    try:
        rc = proc.wait(timeout=grace)
        time.sleep(0.5)  # 等 drain thread 把最後的錯誤行印完
        return None, f"dvt simulate-location 結束, 結束碼 {rc} (原因看上面 [dvt] 的行)"
    except subprocess.TimeoutExpired:
        return proc, None  # 還在跑, 就是成功


_warned_proc = None


def _watch_sim():
    """背景監看模擬程序: 它中途結束 = 定位已還原, 馬上在視窗警告,
    不然橋接會一直以為定位還在, 手機卻早已跳回真實位置。
    死了的程序順手清掉, 免得下次寫入把它當成還在跑 (grace=0 就印假成功)。"""
    global _warned_proc, _sim_proc, _sim_mode
    while True:
        time.sleep(5)
        proc = _sim_proc
        if proc is not None and proc.poll() is not None and proc is not _warned_proc:
            _warned_proc = proc
            if proc is _sim_proc:
                _sim_proc, _sim_mode = None, None
            print(f"[橋接] 注意: 模擬程序已結束 (結束碼 {proc.returncode}), iPhone 定位可能已還原, 請到中控台再瞬移一次", flush=True)


def set_location(lat, lng):
    global _sim_proc, _sim_mode, _last_applied, _last_restart
    # 手機被標成 missing 時 (例如剛拔 USB), 先重找一次再決定: 可能已改走
    # Wi-Fi, _watch_phone 的 15 秒巡檢不一定剛跑過。_refresh_phone 有 10 秒
    # 節流, 路線每秒推播時不會一直掃 Bonjour。重找還找不到才報失敗, 不跑 dvt
    # (2026-11-20 凌晨就是沒擋好: 啟動即報找不到 iPhone, 兩次寫入都印成功,
    #  dvt 隨即報 Device is not connected、結束碼 1, 定位還原)。
    # 舊版只在 DEVICE_UDID 是空的才擋, 拔過 USB 後 UDID 還留著舊值, 擋不住。
    if _phone_state == "missing" and not _refresh_phone():
        print("[橋接] 失敗: 找不到 iPhone, 定位沒寫進去", flush=True)
        print("[橋接] 請檢查 USB 有沒有接好、手機有沒有解鎖亮屏、跳「信任此電腦」有沒有點信任; 插好後 15 秒內會自動偵測, 不用重開橋接", flush=True)
        return False
    # 路線播放中每秒推播一次, 但 dvt 模擬重開一次要 1-2 秒才生效:
    # 每秒重開會讓手機定位在真實/模擬之間一直跳, 遊戲就不同步。
    # 所以只動了一點點就不用重開 (模擬還在跑、位置差不多, 遊戲看不出來);
    # 移動超過 5 公尺、且距離上次重開超過 2 秒, 才重開一次。
    # 超過 10 秒沒重開也重開一次, 免得模擬停在太舊的位置。
    # 但一次跳超過 100 公尺是瞬移, 立刻重開, 不用等。
    if _sim_proc is not None and _sim_proc.poll() is None and _last_applied is not None:
        elapsed = time.time() - _last_restart
        d = _dist_m(_last_applied, (lat, lng))
        if d < 100 and (elapsed < 2 or (d < 5 and elapsed < 10)):
            return True
    print(f"[橋接] 寫入 iPhone: {lat}, {lng}", flush=True)
    # 只有模擬程序「還活著」才算跑著: 死了的程序還掛在 _sim_proc 上時,
    # 絕對不能走 grace=0 (不等確認就印成功), 否則就是 11/19 凌晨第二次寫入的假成功。
    was_running = _sim_proc is not None and _sim_proc.poll() is None
    _stop_sim()  # 先停掉上一個位置的模擬, 再開新的
    # 路線播放中換位置: 上一個模擬剛剛還在跑 (環境驗過是好的), 不用再等 8 秒確認;
    # 冷啟動 (剛開橋接、剛還原) 才等 8 秒, 確認程序沒崩。
    proc, err = _start_dvt(lat, lng, grace=0 if was_running else 8)
    if proc is not None:
        _sim_proc, _sim_mode = proc, "dvt"
        _last_applied = (lat, lng)
        _last_restart = time.time()
        print("[橋接] 成功, iPhone 現在就是這個位置 (模擬程序在背景跑著, 不要關這個視窗)", flush=True)
        return True
    # dvt 不行: 可能手機剛從 USB 換到 Wi-Fi (UDID 沒變, 但走的通道變了)。
    # 強制重找一次確認手機還在, 在就用同一支 UDID 再試一次 dvt (dvt 會自己
    # 走 tunnel fallback); 找不到就不重試, 直接進舊版/失敗流程。
    # 舊版這裡只在 DEVICE_UDID 是空的才重找, 拔過 USB 後 UDID 還留著舊值,
    # 這段永遠跑不到, Wi-Fi 重試是死碼。
    if _refresh_phone(force=True):
        proc, err = _start_dvt(lat, lng)
        if proc is not None:
            _sim_proc, _sim_mode = proc, "dvt"
            _last_applied = (lat, lng)
            _last_restart = time.time()
            print("[橋接] 成功, iPhone 現在就是這個位置 (模擬程序在背景跑著, 不要關這個視窗)", flush=True)
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
    global _last_applied, _last_restart
    _last_applied = None
    _last_restart = 0.0
    print("[橋接] 還原 iPhone 真實定位", flush=True)
    _stop_sim()  # 砍掉背景模擬程序, 定位就跟著還原
    # 再補一次 clear 指令, 清掉舊版模式可能留下的模擬 (失敗也沒關係)
    run(_pmd3_cmd() + ["developer", "dvt", "simulate-location", "clear"], timeout=30)
    run(_pmd3_cmd() + ["developer", "simulate-location", "clear"], timeout=30)
    print("[橋接] 已還原", flush=True)
    return True


def serve():
    global _sio
    try:
        import socketio
    except ImportError:
        print("缺少 python-socketio, 請先跑 install.bat (pip install -r requirements.txt)")
        sys.exit(1)

    sio = socketio.Client(reconnection=True, reconnection_attempts=0)
    _sio = sio

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

    _ensure_device_id()  # 沒手動設 DEVICE_ID 時, 用手機 UDID 當裝置 ID
    print(f"[橋接] 啟動, 裝置 {DEVICE_ID} ({DEVICE_NAME}), 後端 {BACKEND_URL}")
    print("[橋接] 請確認 iPhone 已用 USB 接上並信任電腦, 然後到中控台選這台裝置")
    threading.Thread(target=_watch_sim, daemon=True).start()
    threading.Thread(target=_watch_phone, daemon=True).start()  # 每 15 秒檢查 iPhone 在不在
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
        _ensure_device_id()  # 測試也用手機 UDID 當 ID, 指到同一支手機
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
