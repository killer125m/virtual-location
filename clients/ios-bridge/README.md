# iPhone 橋接程式 (Windows 用, 無越獄)

iPhone 本身不准 App 改系統 GPS, 所以一定要由電腦當橋接。
這台 Windows 電腦監聽中控後端, 收到座標就用 pymobiledevice3 透過 USB 寫入 iPhone。

## 前置條件

- Windows 電腦, Python 3.11 以上 (安裝時勾 Add to PATH)
- iTunes (Apple 官網版, 裝 Apple Mobile Device 驅動用, Microsoft Store 版驅動有時認不到)
- iPhone 用 USB 傳輸線接電腦 (不要只用充電線, 要能傳資料)
- iPhone 開開發者模式: 設定 > 隱私權與安全性 > 開發者模式 > 開啟, 重開機
- 中控後端在跑 (Docker 或 `npm start`, http://localhost:3000)

## 安裝與啟動

1. 雙擊 `install.bat` (裝 pymobiledevice3 + python-socketio)
2. iPhone 接 USB, 點「信任此電腦」
3. 雙擊 `test.bat` 先測一次: 會列出裝置, 再把定位改到台北 101, 打開 iPhone 地圖 App 應該就在台北 101。測試會佔住這個視窗, 看完按 Ctrl+C 就會停止並還原
4. 還原: `python ios_bridge.py --clear` (關掉橋接視窗也會自動還原)
5. 雙擊 `start.bat`, 到 http://localhost:3000 選 `ios-bridge-01` 這台裝置, 瞬移 / 播路線

## 常用指令

```bash
python ios_bridge.py --list
python ios_bridge.py --test 25.0339 121.5645
python ios_bridge.py --clear
python ios_bridge.py
```

環境變數: `BACKEND_URL` (預設 http://localhost:3000), `DEVICE_ID` (預設 ios-bridge-01), `DEVICE_NAME`。

## 常見問題

- `找不到 pymobiledevice3`: 先跑 install.bat, 或檢查 Python 有沒有加到 PATH。
- `沒有看到裝置` / `usbmux list` 是空的: 換一條線、換一個 USB 孔、重插、確認 iPhone 有點信任、iTunes 有裝好。
- `simulate-location` 失敗: 確認開發者模式有開、iPhone 沒有鎖定畫面、USB 沒鬆掉。iOS 大版本剛升級時, pymobiledevice3 可能要等更新才能支援新版, 先跑 `pip install -U pymobiledevice3` 試試。
- 定位改完 iPhone 地圖沒動: 等幾秒, 或把地圖 App 滑掉重開。iOS 17+ 的模擬是靠背景程序撐著, 橋接視窗關掉定位就會還原, 所以測試和同步時視窗不要關。
- 這個橋接程式的黑視窗不要關, 關掉就斷線, 同時也會把 iPhone 還原回真實定位。
