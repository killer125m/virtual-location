# Chrome 擴充功能 (Manifest V3, 2026-11-17 補上)

只改「這個瀏覽器分頁裡的網頁」讀到的定位, 改不了手機 App、也改不了 IP / Wi-Fi 定位。
做法跟 Android App 一樣, 每 2 秒輪詢後端, 不用 Socket.io、不用額外裝東西。

## 安裝

1. 後端先跑起來 (Docker 或 `npm start`, http://localhost:3000)
2. Chrome 開 `chrome://extensions`, 右上開「開發人員模式」
3. 「載入未封裝項目」, 選 `clients/chrome-extension/` 這個資料夾
4. 隨便開一個網頁, 到中控台選 `chrome-ext-01` 這台裝置, 瞬移 / 播路線

## 怎麼動的

- `bridge.js` (隔離世界): 每 2 秒 `GET /api/devices` 問後端, 找到 `chrome-ext-01`
  的座標就用 `window.postMessage` 傳給主世界。開頁面時也會自己 `POST /api/devices`
  註冊, 所以中控台一定看得到它。
- `content.js` (MAIN 世界, `document_start`): 在網頁程式之前先蓋掉
  `navigator.geolocation.getCurrentPosition / watchPosition`, 有座標就回假的,
  沒座標 (後端還原了) 就走回真實定位。
- `popup.html`: 點工具列圖示看目前座標, 可按「還原真實定位」。

## 注意

- 後端位址寫死 `http://localhost:3000`, 擴充功能要跟後端同一台電腦才有用。
  後端在別台電腦的話, 改 `bridge.js` / `popup.js` 開頭的 `BACKEND_URL` 再重新載入。
- 有些網站除了 JS 定位還會用 IP 定位, 那種這個擴充功能改不了。
