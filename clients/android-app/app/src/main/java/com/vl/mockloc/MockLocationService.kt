package com.vl.mockloc

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat

/**
 * 前台服務: 一直在背景跑, 每 2 秒問後端一次, 有新座標就寫入 Mock Location。
 * 沒有前台服務, App 被系統殺掉 / 滑掉後定位就會停住。
 * 用 Intent 傳 backendUrl / deviceId, 停止時送 ACTION_STOP。
 */
class MockLocationService : Service() {
    companion object {
        const val ACTION_STOP = "com.vl.mockloc.STOP"
        const val EXTRA_URL = "backendUrl"
        const val EXTRA_DEVICE_ID = "deviceId"
        const val EXTRA_LAT = "lat"
        const val EXTRA_LNG = "lng"
    }

    private var running = false
    private var thread: Thread? = null
    private lateinit var provider: MockLocationProvider

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        provider = MockLocationProvider(this)
        val channel = NotificationChannel("mockloc", "虛擬定位", NotificationManager.IMPORTANCE_LOW)
        (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
        val notification: Notification = NotificationCompat.Builder(this, "mockloc")
            .setContentTitle("虛擬定位執行中")
            .setContentText("正在同步中控台的座標")
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .build()
        startForeground(1, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        val url = intent?.getStringExtra(EXTRA_URL) ?: return START_NOT_STICKY
        val deviceId = intent.getStringExtra(EXTRA_DEVICE_ID) ?: return START_NOT_STICKY
        // 手動模式: Intent 有帶 lat/lng 就只定那一點, 不問後端
        val manualLat = if (intent.hasExtra(EXTRA_LAT)) intent.getDoubleExtra(EXTRA_LAT, 0.0) else null
        val manualLng = if (intent.hasExtra(EXTRA_LNG)) intent.getDoubleExtra(EXTRA_LNG, 0.0) else null
        if (running) return START_STICKY
        running = true
        try { provider.start() } catch (e: SecurityException) {
            // 沒選模擬位置應用程式, Service 會停, MainActivity 會提示
            stopSelf()
            return START_NOT_STICKY
        }
        val backend = BackendClient(url)
        backend.register(deviceId, android.os.Build.MODEL ?: deviceId)
        thread = Thread {
            var last: Pair<Double, Double>? = null
            if (manualLat != null && manualLng != null) {
                last = Pair(manualLat, manualLng)
                provider.set(manualLat, manualLng)
            }
            while (running) {
                try {
                    // 手動模式不輪詢, 只每秒重送一次同一點
                    val target = if (manualLat != null && manualLng != null) {
                        Pair(manualLat, manualLng)
                    } else {
                        backend.fetchTarget(deviceId)
                    }
                    if (target != null) {
                        last = target
                        provider.set(target.first, target.second)
                    } else if (last != null) {
                        provider.set(last.first, last.second)
                    }
                } catch (_: Exception) {
                }
                try { Thread.sleep(1000) } catch (_: InterruptedException) { break }
            }
        }
        thread?.start()
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        thread?.interrupt()
        try { provider.stop() } catch (_: Exception) {}
        super.onDestroy()
    }
}
