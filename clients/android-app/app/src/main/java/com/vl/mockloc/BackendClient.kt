package com.vl.mockloc

import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * 後端連線: 用最簡單的 REST 輪詢, 不用 Socket.io Java 客戶端, 依賴最少。
 * 流程:
 *  1. POST /api/devices {id, type:"android", name} 註冊
 *  2. 每 2 秒 GET /api/devices, 找自己這台的 location, 有新座標就回傳
 * 中控台瞬移 / 播路線時, 後端會更新 location, App 輪詢到就跟著動。
 */
class BackendClient(private val baseUrl: String) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    private fun url(path: String) = baseUrl.trimEnd('/') + path

    fun register(deviceId: String, name: String): Boolean {
        return try {
            val body = okhttp3.RequestBody.create(
                okhttp3.MediaType.parse("application/json"),
                JSONObject().apply {
                    put("id", deviceId)
                    put("type", "android")
                    put("name", name)
                }.toString()
            )
            val req = Request.Builder().url(url("/api/devices")).post(body).build()
            client.newCall(req).execute().use { it.isSuccessful }
        } catch (_: Exception) {
            false
        }
    }

    /** 回傳這台裝置目前在後端的目標座標, 沒有就回 null */
    fun fetchTarget(deviceId: String): Pair<Double, Double>? {
        return try {
            val req = Request.Builder().url(url("/api/devices")).get().build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return null
                val arr = org.json.JSONArray(resp.body()?.string() ?: return null)
                for (i in 0 until arr.length()) {
                    val d = arr.getJSONObject(i)
                    if (d.optString("id") != deviceId) continue
                    val loc = d.optJSONObject("location") ?: return null
                    return Pair(loc.getDouble("lat"), loc.getDouble("lng"))
                }
                null
            }
        } catch (_: Exception) {
            null
        }
    }
}
