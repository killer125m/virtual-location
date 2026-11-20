"""不連真機, 測 _find_phone 的 UDID 解析與 _apply_phone 的裝置 ID。

2026-11-20: iPhone 15 Pro 的 UDID 是新款 8 碼-16 碼格式
(00008110-000C2A3B4D5E6F7A), 舊版正則只認 40 碼, 偵測永遠失敗。
"""
import sys

sys.path.insert(0, "/home/hatch/workspace/virtual-location/clients/ios-bridge")
import ios_bridge as b

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS - {name}")
    else:
        failed += 1
        print(f"FAIL - {name}")


def make_run(mapping):
    def fake(cmd, timeout=60):
        return mapping.get(tuple(cmd[1:]), (False, ""))

    return fake


NEW_UDID = "00008110-000C2A3B4D5E6F7A"
OLD_UDID = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"

# 1. 新款 UDID 經 --simple 找到
b.run = make_run({("usbmux", "list", "--simple"): (True, f'["{NEW_UDID}"]')})
udid, t = b._find_phone()
check("1. 新款 UDID 經 --simple 找到", udid == NEW_UDID and t == "USB")

# 2. 一般 list 印得出 UDID 但結束碼非零, 還是要找到
b.run = make_run({
    ("usbmux", "list", "--simple"): (False, ""),
    ("usbmux", "list"): (False, f'[{{"Identifier": "{NEW_UDID}", "UniqueDeviceID": "{NEW_UDID}"}}]'),
})
udid, t = b._find_phone()
check("2. 結束碼非零但有 UDID 還是找到", udid == NEW_UDID and t == "USB")

# 3. 舊款 40 碼 UDID
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, f"UDID: {OLD_UDID}"),
})
udid, t = b._find_phone()
check("3. 舊款 40 碼 UDID 找到", udid == OLD_UDID and t == "USB")

# 4. 什麼都沒有
b.run = make_run({})
udid, t = b._find_phone()
check("4. 沒裝置回空", udid == "" and t is None)

# 5. 新款 UDID 的裝置 ID 取連字號後段前 8 碼 (00008110 是共用前綴)
b.DEVICE_ID_FROM_ENV = False
b._apply_phone(NEW_UDID, "USB")
check("5. 新款 UDID 裝置 ID", b.DEVICE_ID == "ios-000c2a3b")
print("   got:", b.DEVICE_ID)

# 6. 舊款 UDID 的裝置 ID 維持前 8 碼
b._apply_phone(OLD_UDID, "USB")
check("6. 舊款 UDID 裝置 ID", b.DEVICE_ID == "ios-a1b2c3d4")
print("   got:", b.DEVICE_ID)

# 7. 找不到手機時 set_location 回 False、不跑 dvt (承接上次修復)
b.DEVICE_UDID = ""
b._phone_state = "missing"
calls = []
orig_popen = b.subprocess.Popen


def _no_popen(*a, **k):
    calls.append(a)
    raise RuntimeError("should not run dvt")


b.subprocess.Popen = _no_popen
try:
    ok = b.set_location(24.0, 120.0)
except RuntimeError:
    ok = "RAN_DVT"
check("7. 找不到手機 set_location 回 False 不跑 dvt", ok is False and not calls)
b.subprocess.Popen = orig_popen

# 8. grace=0 時立刻死掉的程序要回 None, 不要印成功
# (2026-11-20 10:01/10:08 拔線後: dvt 報 Device not found, 舊版 grace=0
#  不等確認就印成功。修法是等 1 秒再確認, 不是關 stdin: 模擬開始後
#  pymobiledevice3 停在 "Press ENTER to exit>" 等人按 Enter, 定位靠這個
#  程序活著才留得住, stdin 關掉 (DEVNULL) 讀到 EOF 立刻結束碼 0、定位還原)
import subprocess as _sp


class FakeDeadProc:
    def __init__(self, *a, **k):
        self.kwargs = k
        self.returncode = 1
        self.stderr = iter(["Device not found: usbmux has no device matching udid X\n"])

    def poll(self):
        return 1

    def wait(self, timeout=None):
        return 1


seen = {}


def _fake_popen_dead(*a, **k):
    seen.update(k)
    return FakeDeadProc(*a, **k)


b.subprocess.Popen = _fake_popen_dead
proc, err = b._start_dvt(24.0, 120.0, grace=0)
check("8. grace=0 立刻死掉回 None", proc is None and err is not None)
check("8b. stdin 用 PIPE 一直開著 (模擬靠程序活著才留得住)", seen.get("stdin") is _sp.PIPE)

# 9. 拔線後寫入: 舊程序還活著 (was_running) 但新程序立刻死 -> 回 False, 不印成功


class FakeAliveProc:
    def __init__(self, *a, **k):
        self.returncode = None
        self.stderr = iter([])

    def poll(self):
        return None

    def wait(self, timeout=None):
        # 還在跑: 模擬 _start_dvt grace>0 時 wait 逾時 (TimeoutExpired)
        raise _sp.TimeoutExpired("fake", timeout)

    def terminate(self):
        pass

    def kill(self):
        pass


b._sim_proc = FakeAliveProc()
b._sim_mode = "dvt"
b._last_applied = None
b.DEVICE_UDID = "00008130-001E59222E60001C"
b._phone_state = "missing"
b.run = lambda cmd, timeout=60: (False, "Device not found")
import io
import contextlib

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ok = b.set_location(24.1, 120.6)
out = buf.getvalue()
check("9. 拔線後寫入回 False 且不印成功", ok is False and "成功" not in out)
print("   輸出:", out.replace("\n", " | ")[:200])
b.subprocess.Popen = orig_popen
b._sim_proc = None

# 10. Wi-Fi 經 usbmux --network --simple 找到 (USB 兩步都沒東西)
import json as _json

WIFI_UDID = "00008130-001E59222E60001C"
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, "[]"),
    ("usbmux", "list", "--network", "--simple"): (True, f'["{WIFI_UDID}"]'),
})
udid, t = b._find_phone()
check("10. Wi-Fi 經 usbmux --network --simple 找到", udid == WIFI_UDID and t == "Wi-Fi")

# 11. Wi-Fi 經 remote browse 的 wifi[].identifier 找到
# (11.57.0 的 remote 沒有 list 子命令, 舊版 `remote list` 只會報錯,
#  所以 Wi-Fi 偵測以前永遠跑不到這裡)
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, "[]"),
    ("usbmux", "list", "--network", "--simple"): (True, "[]"),
    ("remote", "browse", "--timeout", "2"): (True, _json.dumps({"usb": [], "wifi": [{"address": "192.168.1.5", "port": 0, "identifier": WIFI_UDID}]} )),
})
udid, t = b._find_phone()
check("11. Wi-Fi 經 remote browse wifi identifier 找到", udid == WIFI_UDID and t == "Wi-Fi")

# 12. remote browse 只有 usb 區有 UDID 時算 USB
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, "[]"),
    ("usbmux", "list", "--network", "--simple"): (True, "[]"),
    ("remote", "browse", "--timeout", "2"): (True, _json.dumps({"usb": [{"address": "fd00::1", "port": 1, "UniqueDeviceID": WIFI_UDID}], "wifi": []} )),
})
udid, t = b._find_phone()
check("12. remote browse usb 區算 USB", udid == WIFI_UDID and t == "USB")

# 13. Wi-Fi 經 bonjour mobdev2 找到 (前面都沒東西)
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, "[]"),
    ("usbmux", "list", "--network", "--simple"): (True, "[]"),
    ("remote", "browse", "--timeout", "2"): (True, '{"usb": [], "wifi": []}'),
    ("bonjour", "mobdev2", "--timeout", "2"): (True, f'[{{"UniqueDeviceID": "{WIFI_UDID}"}}]'),
})
udid, t = b._find_phone()
check("13. Wi-Fi 經 bonjour mobdev2 找到", udid == WIFI_UDID and t == "Wi-Fi")

# 14. 拔線後寫入: 狀態 missing, 但 Wi-Fi 找得到手機, 要重找後寫入成功
# (舊版: DEVICE_UDID 還留著舊值, fail-fast 擋不住, dvt 拿舊 UDID 去寫就失敗)


def _fake_popen_alive(*a, **k):
    return FakeAliveProc(*a, **k)


b._last_discovery = 0.0
b._phone_state = "missing"
b.DEVICE_UDID = WIFI_UDID
b._sim_proc = FakeAliveProc()
b._sim_mode = "dvt"
b._last_applied = None
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, "[]"),
    ("usbmux", "list", "--network", "--simple"): (True, f'["{WIFI_UDID}"]'),
})
b.subprocess.Popen = _fake_popen_alive
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ok = b.set_location(24.1, 120.6)
out = buf.getvalue()
check("14. missing 但 Wi-Fi 找得到就寫入成功", ok is True and "成功" in out and "Wi-Fi" in out)
print("   輸出:", out.replace("\n", " | ")[:200])
b.subprocess.Popen = orig_popen
b._sim_proc = None

# 15. dvt 先失敗 (Device not found), 重找確認手機還在就再試一次並成功
# (舊版: `if not DEVICE_UDID` 在拔線後永遠不成立, Wi-Fi 重試是死碼)
_calls = {"n": 0}


def _fake_popen_dead_then_alive(*a, **k):
    _calls["n"] += 1
    if _calls["n"] == 1:
        return FakeDeadProc(*a, **k)
    return FakeAliveProc(*a, **k)


b._last_discovery = 0.0
b._phone_state = "connected"
b.DEVICE_UDID = WIFI_UDID
b._sim_proc = FakeAliveProc()
b._sim_mode = "dvt"
b._last_applied = None
b.run = make_run({
    ("usbmux", "list", "--simple"): (True, "[]"),
    ("usbmux", "list"): (True, "[]"),
    ("usbmux", "list", "--network", "--simple"): (True, f'["{WIFI_UDID}"]'),
})
b.subprocess.Popen = _fake_popen_dead_then_alive
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    ok = b.set_location(24.1, 120.6)
out = buf.getvalue()
check("15. dvt 失敗後重找再試一次成功", ok is True and "成功" in out)
print("   輸出:", out.replace("\n", " | ")[:200])
b.subprocess.Popen = orig_popen
b._sim_proc = None

# 17. 冷啟動驗證預設 3 秒 (舊版 8 秒, 每次冷啟動都固定等滿才回成功)
import inspect as _inspect

check("17. _start_dvt 預設 grace 是 3 秒", _inspect.signature(b._start_dvt).parameters["grace"].default == 3)

# 18. 手機狀態回報: _apply_phone 記下 transport, 並經 socket 回報給後端
class FakeSio:
    def __init__(self):
        self.connected = True
        self.emitted = []

    def emit(self, event, data):
        self.emitted.append((event, data))


b._sio = FakeSio()
b.DEVICE_ID_FROM_ENV = False
b._apply_phone(WIFI_UDID, "Wi-Fi")
check("18. _apply_phone 記下 transport 並回報 phone:state",
      b._phone_transport == "Wi-Fi" and any(e == "phone:state" and d.get("phoneState") == "connected" and d.get("transport") == "Wi-Fi" for e, d in b._sio.emitted))
b._sio = None

# 16. 模擬真實 pymobiledevice3 的 stdin 行為: 模擬開始後它停在
# "Press ENTER to exit>" 等輸入; stdin 開著 (PIPE) 就一直活著、定位留得住,
# stdin 關掉 (DEVNULL) 讀到 EOF 立刻結束碼 0、定位還原。
# (2026-11-20 11:24: c39e5a6 用 DEVNULL, 每次寫入成功後程序立刻結束;
#  舊測試沒模擬 stdin 行為所以沒抓到, 這關就是補給它的。)
class FakeWaitReturnProc:
    def __init__(self, *a, **k):
        self.stdin_mode = k.get("stdin")
        self.returncode = None
        self.stderr = iter([])

    def poll(self):
        return None if self.stdin_mode is _sp.PIPE else 0

    def wait(self, timeout=None):
        if self.stdin_mode is _sp.PIPE:
            raise _sp.TimeoutExpired("fake", timeout)
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


b.subprocess.Popen = lambda *a, **k: FakeWaitReturnProc(*a, **k)
proc, err = b._start_dvt(24.0, 120.0, grace=8)
check("16. 成功程序在 grace 內不死、回傳活著的程序", proc is not None and err is None)
# 反向: 同一個假程序若 stdin 是 DEVNULL 就會立刻結束 (c39e5a6 的 bug)
dead = FakeWaitReturnProc(stdin=_sp.DEVNULL)
check("16b. stdin 關掉時真實程序會立刻結束碼 0 (DEVNULL 不能用)", dead.poll() == 0 and dead.wait(timeout=8) == 0)
b.subprocess.Popen = orig_popen

print(f"\n{passed}/{passed + failed} 通過")
sys.exit(1 if failed else 0)
