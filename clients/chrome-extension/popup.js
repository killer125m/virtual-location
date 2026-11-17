const BACKEND_URL = "http://localhost:3000";
const DEVICE_ID = "chrome-ext-01";

async function refresh() {
  const el = document.getElementById("status");
  try {
    const r = await fetch(`${BACKEND_URL}/api/devices`);
    const devices = await r.json();
    const me = devices.find((d) => d.id === DEVICE_ID);
    if (!me) { el.textContent = "中控台還沒看到這台裝置, 先開一個網頁再回來看"; return; }
    el.textContent = me.location
      ? `目前座標: ${me.location.lat}, ${me.location.lng}`
      : "目前是真實定位 (中控台還沒指定座標)";
  } catch (_) {
    el.textContent = "連不上後端, 先確認中控台在跑 (http://localhost:3000)";
  }
}

document.getElementById("clear").onclick = async () => {
  await fetch(`${BACKEND_URL}/api/devices/${DEVICE_ID}/location/clear`, { method: "POST" });
  refresh();
};
document.getElementById("open").onclick = () => chrome.tabs.create({ url: BACKEND_URL });
refresh();
