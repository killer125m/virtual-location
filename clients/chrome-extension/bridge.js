// bridge.js — 隔離世界 (isolated world) 的 content script。
// 負責跟後端溝通 (不受網頁 CSP 擋), 再用 window.postMessage 把座標
// 傳給 MAIN 世界的 content.js (那邊才能碰到網頁真正的 navigator)。
// 做法跟 Android App 一樣: 每 2 秒輪詢 GET /api/devices, 不用 Socket.io。
const BACKEND_URL = "http://localhost:3000";
const DEVICE_ID = "chrome-ext-01";

let lastSent = "";

async function register() {
  try {
    await fetch(`${BACKEND_URL}/api/devices`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: DEVICE_ID, type: "web", name: "Chrome 擴充功能" }),
    });
  } catch (_) { /* 後端還沒開, 下次輪詢再試 */ }
}

async function poll() {
  try {
    const r = await fetch(`${BACKEND_URL}/api/devices`, { cache: "no-store" });
    if (!r.ok) return;
    const devices = await r.json();
    const me = devices.find((d) => d.id === DEVICE_ID);
    const target = me && me.location
      ? { lat: me.location.lat, lng: me.location.lng }
      : null;
    const key = JSON.stringify(target);
    if (key !== lastSent) {
      lastSent = key;
      window.postMessage({ type: "VL_TARGET", target }, "*");
    }
  } catch (_) { /* 後端沒開就等下次 */ }
}

register();
poll();
setInterval(poll, 2000);
