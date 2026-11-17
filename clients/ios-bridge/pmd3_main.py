"""pymobiledevice3 命令列入口的包裝, 供 PyInstaller 打包成 pymobiledevice3.exe。
ios_bridge.py 打包後會呼叫同目錄的這個 exe, 而不是 PATH 上的 pymobiledevice3。"""
try:
    from pymobiledevice3.__main__ import main
except ImportError:
    try:
        from pymobiledevice3.cli import cli as main
    except ImportError:
        from pymobiledevice3.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
