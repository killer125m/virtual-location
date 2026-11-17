# 跨平台虛擬定位系統 · 原型

雲端中控台 (Web UI) + 地理編碼 API + 各平台原生客戶端，分離式設計。

## 架構

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

## 快速啟動 (本機)

```bash
cd backend
npm install
npm start
# 開 http://localhost:3000
```

## Docker 啟動 (推薦, 重開機自動重啟)

前提: 電腦裝好 Docker Desktop, 並設成開機自動啟動。

```bash
cd virtual-location
docker compose up -d --build
# 開 http://localhost:3000
```

Windows 一鍵版: 雙擊 `docker-start.bat` 就好。

原理: `docker-compose.yml` 裡設了 `restart: unless-stopped`, 容器會跟著 Docker 一起重啟, 不用再手動 `npm start`。常用指令:

```bash
docker compose ps            # 看有沒有在跑
docker compose logs -f       # 看 Log
docker compose down          # 停掉
docker compose up -d --build # 改完程式碼後重建
```

預設用 Nominatim (OpenStreetMap) 做地理編碼，免 Key，適合測試。
要換 Google (台灣門牌支援最好)，設定環境變數：

```bash
GOOGLE_API_KEY=你的Key PORT=3000 npm start
```

## API

| 方法 | 路徑 | 說明 |
|---|---|---|
| GET | /health | 健康檢查、目前 Geocoder |
| GET | /api/geocode?q=台中市南區興大路145號 | 地址轉座標，回傳候選清單 |
| GET | /api/devices | 裝置列表 |
| POST | /api/devices {id,type,name} | 註冊裝置，type: web / android / ios-bridge |
| POST | /api/devices/:id/location {lat,lng} | 瞬移 |
| POST | /api/devices/:id/location/clear | 還原真實定位 |
| POST | /api/devices/:id/route {waypoints,speedKmh,loop} | 路線模擬，後端每秒插值推播 |
| POST | /api/devices/:id/route/stop | 停止路線 |
| GET/POST | /api/bookmarks | 常用地點書籤 |

WebSocket 事件：`register`, `location:update`, `location:clear`, `devices:update`, `route:start`, `route:stop`

## 測試

```bash
curl "http://localhost:3000/api/geocode?q=台中市南區興大路145號"
curl http://localhost:3000/api/devices
curl -X POST http://localhost:3000/api/devices -H 'Content-Type: application/json' -d '{"id":"android-pixel-01","type":"android","name":"Pixel 8"}'
curl -X POST http://localhost:3000/api/devices/android-pixel-01/location -H 'Content-Type: application/json' -d '{"lat":24.1235,"lng":120.6753}'
```

## 各平台客戶端接法 (摘要)

- **Chrome Extension (MV3)**: Content Script 在 `document_start`、`world: MAIN` 覆寫 `navigator.geolocation.getCurrentPosition / watchPosition`, 隔離世界的 bridge 每 2 秒輪詢後端更新座標 (跟 Android 一樣的做法, 不用 Socket.io)。只對該分頁有效。見 `clients/chrome-extension/` (完整擴充功能, 2026-11-17 補上, 載入未封裝項目就能用)。
- **Android**: 開開發人員選項，設為模擬位置應用程式，`addTestProvider(GPS_PROVIDER)` + 每秒 `setTestProviderLocation()`。見 `clients/android-app/` (完整 Kotlin 專案, 2026-11-17 已做成, 用 Android Studio 開, 有前台服務 + 後端輪詢 + 手動定點)。
- **iOS (無越獄)**: 電腦跑 Python + pymobiledevice3，`developer dvt simulate-location set -- <lat> <lng>`，iPhone 用 USB / Wi-Fi 連電腦。見 `clients/ios-bridge/` (Windows 用, 有 install.bat / start.bat / test.bat, 2026-11-17 已做成完整橋接程式)。

## 限制

- iPhone 本身無合法 API 可改系統 GPS，一定要經過電腦橋接。
- Android 部分 App 會檢查 `isFromMockProvider()`。
- Chrome 擴充只改網頁 JS 定位，改不了 IP / Wi-Fi 定位。
- 本原型用記憶體存狀態，重啟後裝置與 Log 會清空，正式版改 Redis / Postgres。
- 僅供開發測試、QA、Demo 使用。
