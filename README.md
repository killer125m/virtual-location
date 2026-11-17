# 跨平台虛擬定位系統 · 原型

雲端中控台: https://virtual-location.onrender.com
完整操作 SOP: [SOP.md](SOP.md)

## 怎麼用 (往下拉就能看到, 完整版在 SOP.md)

**一般人開網頁就能用, 不用裝東西:**
1. 開 https://virtual-location.onrender.com, 等它顯示「WebSocket 已連線」
   (免費版 15 分鐘沒人用會休眠, 第一次開要等 50 秒以上才醒, 是正常的)
2. 右邊「裝置」選一台要改的裝置, 左邊搜地址或直接點地圖
3. 點「瞬移到選取裝置」就過去了; 要走路線就先加至少 2 個途經點, 按「播放路線」
4. 不用時點「還原定位」; 要刪裝置點它右上角紅色 ✕

**iPhone 一定要電腦當橋接:**
第一次: 裝 iTunes, iPhone 用 USB 接電腦點信任, 開開發者模式並重開機,
到 GitHub Actions 下載 `ios-bridge-exe`, 雙擊 `ios-bridge.exe` 就好,
不用裝 Python。第一次 USB 配對完, 之後同一 Wi-Fi 不插線也會試 Wi-Fi。
黑視窗不要關, 關掉 iPhone 就收不到新位置了。

**Android 裝 App 就能用:**
到 GitHub Actions 下載 `virtual-location-apk` 裝到手機,
開開發人員選項 > 選取模擬位置應用程式 > 選「虛擬定位」,
App 裡後端位址填 `https://virtual-location.onrender.com`, 按開始。

**注意:** 雲端版沒有帳號隔離, 拿到網址的人都能看到同一批裝置、改同一批定位,
只給信任的朋友用, 不要公開貼到網路上。

---

## 開發者說明

雲端中控台 (Web UI) + 地理編碼 API + 各平台原生客戶端, 分離式設計。

### 架構

```
Web 中控台 (backend/public/index.html, Leaflet)
  | REST / WebSocket (Socket.io)
  v
後端 (backend/server.js, Express + Socket.io)
  | WebSocket 推播 location:update
  +--> Chrome Extension: 覆寫 navigator.geolocation
  +--> Android App: LocationManager.addTestProvider / setTestProviderLocation
  +--> iOS 橋接程式: pymobiledevice3 developer dvt simulate-location set
```

### 快速啟動 (本機)

```bash
cd backend
npm install
npm start
# 開 http://localhost:3000
```

### Docker 啟動 (推薦, 重開機自動重啟)

前提: 電腦裝好 Docker Desktop, 並設成開機自動啟動。

```bash
cd virtual-location
docker compose up -d --build
# 開 http://localhost:3000
```

Windows 一鍵版: 雙擊 `docker-start.bat` 就好。

原理: `docker-compose.yml` 裡設了 `restart: unless-stopped`, 容器會跟著 Docker 一起重啟, 不用再手動 `npm start`。

預設用 Nominatim (OpenStreetMap) 做地理編碼, 免 Key, 適合測試。
要換 Google (台灣門牌支援最好), 設定環境變數:

```bash
GOOGLE_API_KEY=你的Key PORT=3000 npm start
```

### API

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | /health | 健康檢查、目前 Geocoder |
| GET | /api/geocode?q=台中市南區興大路145號 | 地址轉座標, 回傳候選清單 |
| GET | /api/devices | 裝置列表 |
| POST | /api/devices {id,type,name} | 註冊裝置, type: web / android / ios-bridge |
| DELETE | /api/devices/:id | 移除裝置 |
| POST | /api/devices/:id/location {lat,lng} | 瞬移 |
| POST | /api/devices/:id/location/clear | 還原真實定位 |
| POST | /api/devices/:id/route {waypoints,speedKmh,loop} | 路線模擬, 後端每秒插值推播 |
| POST | /api/devices/:id/route/stop | 停止路線 |
| GET/POST | /api/bookmarks | 常用地點書籤 |

WebSocket 事件: `register`, `location:update`, `location:clear`, `devices:update`, `route:start`, `route:stop`

### 各平台客戶端接法 (摘要)

- **Chrome Extension (MV3)**: Content Script 在 `document_start`、`world: MAIN` 覆寫 `navigator.geolocation.getCurrentPosition / watchPosition`, 隔離世界的 bridge 每 2 秒輪詢後端更新座標。只對該分頁有效。見 `clients/chrome-extension/`。
- **Android**: 開開發人員選項, 設為模擬位置應用程式, `addTestProvider(GPS_PROVIDER)` + 每秒 `setTestProviderLocation()`。見 `clients/android-app/` (完整 Kotlin 專案)。
- **iOS (無越獄)**: 電腦跑 Python + pymobiledevice3, `developer dvt simulate-location set -- <lat> <lng>`, iPhone 用 USB / Wi-Fi 連電腦。見 `clients/ios-bridge/`。

### 限制

- iPhone 本身無合法 API 可改系統 GPS, 一定要經過電腦橋接。
- Android 部分 App 會檢查 `isFromMockProvider()`。
- Chrome 擴充只改網頁 JS 定位, 改不了 IP / Wi-Fi 定位。
- 本原型用記憶體存狀態, 重啟後裝置與 Log 會清空, 正式版改 Redis / Postgres。
- 僅供開發測試、QA、Demo 使用。
