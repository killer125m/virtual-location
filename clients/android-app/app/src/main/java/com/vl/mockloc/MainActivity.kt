package com.vl.mockloc

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.vl.mockloc.databinding.ActivityMainBinding

/**
 * 主畫面: 填後端位址 + 裝置 ID, 點「開始同步」就啟動前台服務跟著中控台走。
 * 也可以不連後端, 直接填經緯度點「只定這一點」手動測試。
 * 第一次用一定要先去開發人員選項選本 App 為模擬位置應用程式, 否則會報 SecurityException。
 */
class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 電腦跟手機要在同一個 Wi-Fi, 後端位址填電腦的區網 IP, 不要填 localhost
        // 例: 電腦 IP 是 192.168.1.10, 就填 http://192.168.1.10:3000
        binding.etBackend.setText("http://192.168.1.10:3000")
        binding.etDeviceId.setText("android-pixel-01")

        binding.btnPermissions.setOnClickListener {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                    Manifest.permission.POST_NOTIFICATIONS
                ), 1
            )
            Toast.makeText(this, "再去開發人員選項, 把本 App 設為模擬位置應用程式", Toast.LENGTH_LONG).show()
            startActivity(Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS))
        }

        binding.btnStart.setOnClickListener {
            val url = binding.etBackend.text.toString().trim()
            val deviceId = binding.etDeviceId.text.toString().trim()
            if (url.isEmpty() || deviceId.isEmpty()) {
                Toast.makeText(this, "請先填後端位址和裝置 ID", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            val intent = Intent(this, MockLocationService::class.java).apply {
                putExtra(MockLocationService.EXTRA_URL, url)
                putExtra(MockLocationService.EXTRA_DEVICE_ID, deviceId)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            binding.tvStatus.text = "狀態: 同步中 ($deviceId)\n到中控台 http://localhost:3000 選這台裝置瞬移"
            Toast.makeText(this, "已開始同步, 請到中控台操作", Toast.LENGTH_SHORT).show()
        }

        binding.btnManual.setOnClickListener {
            val lat = binding.etLat.text.toString().toDoubleOrNull()
            val lng = binding.etLng.text.toString().toDoubleOrNull()
            if (lat == null || lng == null) {
                Toast.makeText(this, "請先填經緯度", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            val intent = Intent(this, MockLocationService::class.java).apply {
                putExtra(MockLocationService.EXTRA_URL, binding.etBackend.text.toString().trim())
                putExtra(MockLocationService.EXTRA_DEVICE_ID, binding.etDeviceId.text.toString().trim())
                putExtra(MockLocationService.EXTRA_LAT, lat)
                putExtra(MockLocationService.EXTRA_LNG, lng)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            binding.tvStatus.text = "狀態: 已定在 $lat, $lng (手動模式)"
        }

        binding.btnStop.setOnClickListener {
            val intent = Intent(this, MockLocationService::class.java).apply {
                action = MockLocationService.ACTION_STOP
            }
            startService(intent)
            binding.tvStatus.text = "狀態: 已停止, 定位已還原"
            Toast.makeText(this, "已停止並還原", Toast.LENGTH_SHORT).show()
        }
    }
}
