# Android 客戶端 (Kotlin 原生, 全機生效)

用 `LocationManager.addTestProvider / setTestProviderLocation` 覆寫系統 GPS,
所有 App (地圖、打卡、外送等) 都會讀到虛擬座標。

## 前置條件

- Android 手機, Android 8 以上
- 電腦裝 Android Studio (最新版), 第一次開專案會下載 Gradle, 要等一下
- 手機開開發人員選項: 設定 > 關於手機 > 連點「版本號碼」7 次
- 開發人員選項 > 選擇模擬位置應用程式 > 選「虛擬定位」
- 手機跟電腦在同一個 Wi-Fi, 後端在電腦上跑 (Docker 或 `npm start`)

## 編譯與安裝

1. 用 Android Studio 開 `clients/android-app/` 這個資料夾
2. 手機用 USB 接電腦, 點「允許 USB 偵錯」
3. 點 Run (綠色三角形), 選你的手機, App 就會裝上去
4. App 裡點「1. 授權 + 開開發人員選項」, 授權定位, 再去選模擬位置應用程式
5. 後端位址填電腦的區網 IP, 不要填 localhost
   例: 電腦 IP 是 192.168.1.10, 就填 `http://192.168.1.10:3000`
   查電腦 IP: Windows 打 `ipconfig`, 看 Wi-Fi 的 IPv4。
6. 裝置 ID 填 `android-pixel-01` (要跟中控台選的那台一樣)
7. 點「2. 開始同步」, 到 http://localhost:3000 選這台裝置瞬移 / 播路線
8. 不想連後端就用手動測試: 填經緯度點「只定這一點」

## 怎麼知道有沒有生效

打開手機地圖 App, 藍點應該就在你設的虛擬位置。點「停止並還原」後, 藍點會回到真實位置。

## 常見問題

- App 一按開始就閃退 / 沒反應: 99% 是沒選模擬位置應用程式, 回開發人員選項檢查。
- 中控台推了座標但手機不動: 檢查手機跟電腦是不是同一個 Wi-Fi、後端位址是不是電腦區網 IP、防火牆有沒有擋 3000 port。Windows 防火牆要允許 Node / Docker 的 3000。
- 定位一下有一下沒有: 前台服務被系統殺了, 把 App 的電池最佳化關掉, 允許背景執行。
- 部分 App 會檢查 `isFromMockProvider()`, 會知道這是模擬定位, 這是 Android 系統行為, 擋不掉, 測試用途是正常的。
- 定位會一直維持到點「停止並還原」或手機重開機。
