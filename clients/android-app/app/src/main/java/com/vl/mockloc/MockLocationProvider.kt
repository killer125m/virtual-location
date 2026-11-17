package com.vl.mockloc

import android.content.Context
import android.location.Criteria
import android.location.Location
import android.location.LocationManager
import android.os.SystemClock

/**
 * 核心: 用 LocationManager 的 Test Provider 覆寫系統 GPS。
 * 前置: 開發人員選項 > 選擇模擬位置應用程式 > 選「虛擬定位」。
 * 沒有選, set() 會拋 SecurityException。
 * 要每 1 秒重送一次, 否則系統會視為定位過期。
 */
class MockLocationProvider(context: Context) {
    private val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    fun start() {
        try {
            lm.addTestProvider(
                LocationManager.GPS_PROVIDER,
                false, false, false, false, true, true, true,
                Criteria.POWER_LOW, Criteria.ACCURACY_FINE
            )
        } catch (_: IllegalArgumentException) {
            // 已經加過了, 忽略
        }
        lm.setTestProviderEnabled(LocationManager.GPS_PROVIDER, true)
        try {
            lm.addTestProvider(
                LocationManager.NETWORK_PROVIDER,
                false, false, false, false, true, true, true,
                Criteria.POWER_LOW, Criteria.ACCURACY_FINE
            )
            lm.setTestProviderEnabled(LocationManager.NETWORK_PROVIDER, true)
        } catch (_: Exception) {
        }
    }

    fun set(lat: Double, lng: Double) {
        val now = System.currentTimeMillis()
        val elapsed = SystemClock.elapsedRealtimeNanos()
        for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            try {
                val loc = Location(provider).apply {
                    latitude = lat
                    longitude = lng
                    accuracy = 5f
                    time = now
                    elapsedRealtimeNanos = elapsed
                }
                lm.setTestProviderLocation(provider, loc)
            } catch (_: Exception) {
            }
        }
    }

    fun stop() {
        for (provider in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            try { lm.removeTestProvider(provider) } catch (_: Exception) {}
        }
    }
}
