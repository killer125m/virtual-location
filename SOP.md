# 虛擬定位系統 操作 SOP

版本: 2026-11-17 | 雲端中控台網址不公開貼出, 請私訊索取
程式碼: https://github.com/killer125m/virtual-location

## 一、這套系統是什麼

一套跨平台虛擬定位系統, 後端在雲端, 中控台是網頁, 手機端分三種:
- iPhone: 一定要一台電腦當橋接, 用 USB / Wi-Fi 連 iPhone
- Android: 手機裝 App, 自己連雲端, 不用電腦
- Chrome: 擴充功能改瀏覽器定位 (選用)

注意: 雲端版目前沒有帳號隔離, 拿到網址的人都能看到同一批裝置、改同一批定位,
只給信任的朋友用, 不要公開貼到網路上。

## 二、一般使用者: 開網頁就能用

1. 開雲端中控台網址
   免費版 15 分鐘沒人用會休眠, 第一次開要等 50 秒以上才醒, 是正常的, 等它顯示
   「WebSocket 已連線」再操作。
2. 右邊「裝置」選一台要改的裝置 (點一下就會選取, 可複選)。
3. 左邊搜地址, 例: 台中車站, 點一個候選, 或直接點地圖。
   Nominatim 對台灣中文門牌解析較弱, 門牌號查不到時會退階用路名查並標「近似」,
   請自己確認地圖上的點對不對。
4. 點「瞬移到選取裝置」, 選到的裝置就會過去。
5. 走路線: 先把幾個點「加入途經點」(至少 2 點), 設速度, 按「播放路線」,
   裝置會沿路慢慢走, 按「停止」停下來。單一點旁邊的 ✕ 只刪那一點,
   要整條刪掉按「清除路線」; 瞬移到別的地方也會自動停掉跑到一半的路線。
6. 書籤: 常用地點填名稱按「加入書籤」, 下次點書籤就能直接跳過去。
7. 還原: 點「還原定位」, 裝置會回到真實定位。
8. 刪除裝置: 每台裝置右上角紅色 ✕, 點了會問你確認, 確認後移掉。
   真機重連後會再出現, 模擬裝置刪了就不會再出現。

## 三、iPhone 擁有者: 一定要電腦當橋接

### 第一次設定 (只做一次)

1. 電腦裝 iTunes (Apple 官網版, 裝驅動用)。
2. 下載橋接 .exe: GitHub Repo > Releases > Latest build > 下載 `ios-bridge.exe`、`pymobiledevice3.exe`、`README.txt` (三個放同一個資料夾)。
   (舊方法: 裝 Python 3.11+ 勾 Add to PATH, 進 `clients/ios-bridge/` 跑 `install.bat`。)
3. iPhone 用 USB 接電腦, 點「信任此電腦」。
4. iPhone: 設定 > 隱私權與安全性 > 開發者模式 > 開啟, 重開機。
5. 雙擊 `ios-bridge.exe` (或舊方法: `clients/ios-bridge/start-cloud.bat`)。
   它預設連雲端, 不用再設網址。
   看到「已連上後端」就是通了。

### 每天使用

1. 電腦開機, 雙擊 `ios-bridge.exe`, 黑視窗不要關。
2. 開雲端中控台, 選你的 iPhone 橋接 (裝置 ID 是 ios-開頭加手機 UDID 前 8 碼, 每支手機不一樣), 瞬移 / 播路線。
3. 第一次 USB 配對完, 之後手機跟電腦在同一個 Wi-Fi, 不插線也會試 Wi-Fi 連。
   Wi-Fi 連不上時, 改插 USB 再跑一次。
4. 不用時關掉黑視窗, 或在中控台點「還原定位」, iPhone 回到真實定位。

### 常見問題

- 橋接顯示連不上後端: 雲端可能在休眠, 先開一次中控台等它醒, 再重開橋接。
- 寫入失敗 / 找不到裝置: 檢查 USB 有沒有鬆、iPhone 有沒有鎖屏、有沒有點信任、
  開發者模式有沒有開、iOS 剛升級要等 pymobiledevice3 更新。
- 位置改了又跳回去: 橋接黑視窗被關掉了, 或後端重送把真機座標洗掉, 重開橋接再瞬移一次。

## 四、Android 擁有者: 裝 App 就能用

1. 下載 APK: GitHub Repo > Releases > Latest build > 下載 `app-debug.apk`, 傳到手機安裝。
   (手機要允許安裝未知來源 App。)
2. 手機: 設定 > 關於手機 > 連點版本號碼 7 次, 開啟開發人員選項。
3. 設定 > 開發人員選項 > 選取模擬位置應用程式 > 選「虛擬定位」。
4. 開 App, 後端位址填雲端中控台網址,
   裝置 ID 預設 `android-pixel-01`, 按開始。
5. 回雲端中控台, 選那台 Android 裝置, 瞬移 / 播路線。
6. 不用時在 App 按停止, 或在中控台點「還原定位」。

## 五、Chrome 擴充功能 (選用)

1. Chrome 開 `chrome://extensions`, 右上開「開發人員模式」。
2. 點「載入未封裝項目」, 選 `clients/chrome-extension/`。
3. 擴充功能連到雲端後端, 在中控台選 `chrome-ext-01` 就能改瀏覽器定位。

## 六、維運

- 後端程式在 GitHub, 推上 main 後 Render 會自動重新部署, 約 1-2 分鐘生效。
- 本機版: `D:\虛擬定位\virtual-location`, `docker compose up -d --build`,
  開 http://localhost:3000。
- 雲端版: Render 免費版, Oregon, Docker, `/health` 檢查, 環境變數 `GEOCODER=nominatim`。
  用 Google (killer125m@gmail.com) 登入 Render, GitHub 帳號只能用來授權部署,
  不能用來登入 Render。
- 要改程式: 改完推上 GitHub, Render 自動部署; iPhone / Android 客戶端要重新下載新版。
