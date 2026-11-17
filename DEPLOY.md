# 上雲端部署教學 (Render 免費版)

> 先講清楚: 這版上雲後, 任何拿到網址的人都能看到同一批裝置、改同一批定位。
> 還沒有帳號隔離, 所以只適合給你信任的朋友小範圍試用, 不要公開貼到網路上。
> 要真正開放給陌生人用, 下一步要加登入 + 每人自己的裝置列表, 那是另外一版。

## 準備

1. 先把這包程式推到 GitHub (Render 是從 GitHub 拉程式來部署)
   - 在 GitHub 新建一個 Repo, 例: virtual-location
   - 把 `virtual-location/` 裡的檔案全部推上去
   - 不要推 `node_modules/` 和 `.env`
2. 到 https://render.com 註冊, 用 GitHub 登入最快

## 部署

1. Render Dashboard > New > Web Service
2. 選剛才那個 GitHub Repo
3. Render 會自動讀到根目錄的 `render.yaml`, 確認:
   - Environment: Docker
   - Plan: Free
   - Health Check Path: `/health`
4. 按 Create Web Service, 等 3-5 分鐘建置
   第一次會下載 Node 映像檔, 比較久是正常的
5. 建好後 Render 會給你一個公開網址, 例:
   `https://virtual-location-xxxx.onrender.com`
   開它, 應該就看到中控台, 跟本機 http://localhost:3000 長一樣

## 免費版注意

- Free 版 15 分鐘沒人用會休眠, 下次開要等 30-60 秒才醒, 是正常的
- 每月免費額度有限, 只是試用的話夠用
- 重開機、重部署都不用你手動, Render 會自己跑, `restart: unless-stopped` 在雲端是平台在管

## 手機端要改的網址

後端上雲後, 手機端不要再填 localhost, 改填雲端網址:

- iPhone 橋接: 在 `clients/ios-bridge/` 那台電腦, 跑 start.bat 之前先設環境變數,
  或直接改 `start.bat` 裡面加一行:
  ```
  set BACKEND_URL=https://virtual-location-xxxx.onrender.com
  ```
  然後再跑 `python ios_bridge.py`, 也可以直接打:
  ```
  set BACKEND_URL=https://virtual-location-xxxx.onrender.com
  python ios_bridge.py
  ```
  iPhone 還是要用 USB 接那台電腦, 橋接不能離開電腦。

- Android App: App 裡「後端位址」那欄改填雲端網址,
  例: `https://virtual-location-xxxx.onrender.com`
  手機跟電腦不用同一個 Wi-Fi 了, 有網路就能連。

- 中控台: 直接開雲端網址就能用, 不用再開本機 Docker。

## 常見問題

- 開網址顯示 Application Error: 到 Render > Logs 看, 通常是建置還沒跑完, 等一下再重整。
- 中控台搜地址很慢 / 沒反應: 免費版休眠剛醒, 等 1 分鐘, 或 Nominatim 本身慢, 重試一次。
- iPhone 橋接連不上雲端: 檢查 BACKEND_URL 有沒有打錯、後面有沒有多斜線、是不是 https 不是 http。
- 要停掉雲端版: Render Dashboard > 選服務 > Suspend, 要再開就 Resume。
