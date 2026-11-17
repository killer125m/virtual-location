// Android 客戶端核心片段 (Kotlin)
// 前置: 開發人員選項 > 選擇模擬位置應用程式 > 選這個 App
// 權限: ACCESS_MOCK_LOCATION (manifest), ACCESS_FINE_LOCATION
// Flutter 可用 MethodChannel 把 lat/lng 傳進來，再呼叫以下程式碼。
// 後端收到 location:update 後，App 每秒重送一次 setTestProviderLocation，否則系統會視為過期。
import android.content.Context
import android.location.Criteria
import android.location.Location
import android.location.LocationManager
import android.os.SystemClock

class MockLocationProvider(context: Context) {
  private val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
  fun start() {
    try { lm.addTestProvider(LocationManager.GPS_PROVIDER, false, false, false, false, true, true, true, Criteria.POWER_LOW, Criteria.ACCURACY_FINE) } catch (_: Exception) {}
    lm.setTestProviderEnabled(LocationManager.GPS_PROVIDER, true)
  }
  fun set(lat: Double, lng: Double) {
    val loc = Location(LocationManager.GPS_PROVIDER).apply {
      latitude = lat; longitude = lng; accuracy = 5f
      time = System.currentTimeMillis()
      elapsedRealtimeNanos = SystemClock.elapsedRealtimeNanos()
    }
    lm.setTestProviderLocation(LocationManager.GPS_PROVIDER, loc)
  }
  fun stop() { try { lm.removeTestProvider(LocationManager.GPS_PROVIDER) } catch (_: Exception) {} }
}
