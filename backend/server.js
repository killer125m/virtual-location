/**
 * 跨平台虛擬定位系統 - 雲端中控後端原型
 * Node.js + Express + Socket.io
 *
 * 架構: Web 中控台 -> REST / WebSocket -> 本後端 -> WebSocket -> 各 Adapter
 *   - Chrome Extension: 只覆寫 navigator.geolocation
 *   - Android App: LocationManager.addTestProvider / setTestProviderLocation
 *   - iOS 橋接程式: pymobiledevice3 developer dvt simulate-location set
 *
 * 啟動: cd backend && npm install && npm start
 * 開啟: http://localhost:3000
 *
 * 地理編碼: 預設 Nominatim (OpenStreetMap, 免費, 免 Key, 適合測試)
 * 若設定 GOOGLE_API_KEY, 則優先用 Google Geocoding (台灣門牌支援最好)
 */
const express = require('express');
const http = require('http');
const cors = require('cors');
const path = require('path');
const { Server } = require('socket.io');

const PORT = process.env.PORT || 3000;
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || '';
const GEOCODER = process.env.GEOCODER || (GOOGLE_API_KEY ? 'google' : 'nominatim');

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ---- 記憶體狀態 (原型用, 正式版改 Redis / Postgres) ----
const devices = new Map(); // deviceId -> { id, type, name, status, socketId, location, lastSeen, routeTimer }
const bookmarks = [
  { id: 'bm-1', name: '國立中興大學', address: '台中市南區興大路145號', lat: 24.1235, lng: 120.6753 },
  { id: 'bm-2', name: '台北101', address: '台北市信義區信義路五段7號', lat: 25.0339, lng: 121.5645 },
  { id: 'bm-3', name: '台中車站', address: '台中市中區台灣大道一段1號', lat: 24.1368, lng: 120.6848 },
];
const eventLog = [];
function logEvent(type, message, data) {
  const e = { ts: new Date().toISOString(), type, message, data: data || null };
  eventLog.unshift(e);
  if (eventLog.length > 200) eventLog.pop();
  return e;
}
function publicDevice(d) {
  return { id: d.id, type: d.type, name: d.name, status: d.status, location: d.location || null, lastSeen: d.lastSeen };
}
function broadcastDevices() { io.emit('devices:update', [...devices.values()].map(publicDevice)); }
function setLocation(deviceId, loc, mode = 'teleport') {
  const d = devices.get(deviceId);
  if (!d) return null;
  d.location = { ...loc, accuracy: loc.accuracy ?? 5, timestamp: Date.now(), mode };
  d.lastSeen = Date.now();
  io.emit('location:update', { deviceId, location: d.location });
  logEvent('location', `${d.name} -> ${loc.lat}, ${loc.lng}`, { deviceId, ...loc });
  return d.location;
}
function stopRoute(deviceId) {
  // 完全停掉路線: 清計時器 + 清掉儲存的路線狀態 (暫停中的路線也會被清掉)。
  // 回傳有沒有真的停到東西, 呼叫端只在真的停到時才發 route:stop。
  const d = devices.get(deviceId);
  if (!d) return false;
  let stopped = false;
  if (d.routeTimer) { clearInterval(d.routeTimer); d.routeTimer = null; stopped = true; }
  if (d.route) { delete d.route; d.routePaused = false; stopped = true; }
  return stopped;
}
function moveBy(loc, bearingDeg, distM) {
  // 從 loc 沿 bearingDeg 方向走 distM 公尺後的新座標 (大圓目的地公式)
  const R = 6371000, toRad = (x) => x * Math.PI / 180, toDeg = (x) => x * 180 / Math.PI;
  const d = distM / R, br = toRad(bearingDeg);
  const lat1 = toRad(loc.lat), lng1 = toRad(loc.lng);
  const lat2 = Math.asin(Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(br));
  const lng2 = lng1 + Math.atan2(Math.sin(br) * Math.sin(d) * Math.cos(lat1), Math.cos(d) - Math.sin(lat1) * Math.sin(lat2));
  return { lat: toDeg(lat2), lng: toDeg(lng2) };
}
function startJoystickTimer(d) {
  // 搖桿: 每秒沿目前方向前進 (速度 × 推桿幅度), 位置每秒推播, 跟路線同一節奏。
  const j = d.joystick;
  d.joystickTimer = setInterval(() => {
    if (!d.location) return;
    const speedMs = (j.speedKmh * 1000) / 3600 * j.magnitude;
    const bearing = (Math.atan2(j.dx, j.dy) * 180 / Math.PI + 360) % 360;
    const next = moveBy(d.location, bearing, speedMs);
    setLocation(d.id, { lat: next.lat, lng: next.lng, speed: j.speedKmh / 3.6, bearing: Math.round(bearing) }, 'joystick');
  }, 1000);
}
function stopJoystick(deviceId) {
  const d = devices.get(deviceId);
  if (!d) return false;
  let stopped = false;
  if (d.joystickTimer) { clearInterval(d.joystickTimer); d.joystickTimer = null; stopped = true; }
  if (d.joystick) { delete d.joystick; stopped = true; }
  return stopped;
}
function startRouteTimer(d) {
  // 用 d.route 裡存的進度 (segIdx / segPos) 繼續跑, 暫停後再繼續也是從同一點接著走,
  // 不會像重播那樣跳回起點。
  const r = d.route;
  d.routeTimer = setInterval(() => {
    const seg = r.segs[r.segIdx]; r.segPos += r.stepM;
    if (r.segPos >= seg.d) { r.segIdx++; r.segPos = 0; if (r.segIdx >= r.segs.length) { if (r.loop) { r.segIdx = 0; } else { stopRoute(d.id); io.emit('route:stop', { deviceId: d.id }); return; } } }
    const s = r.segs[r.segIdx]; const t = s.d ? r.segPos / s.d : 0;
    const lat = s.from.lat + (s.to.lat - s.from.lat) * t;
    const lng = s.from.lng + (s.to.lng - s.from.lng) * t;
    const bearing = (Math.atan2(s.to.lng - s.from.lng, s.to.lat - s.from.lat) * 180 / Math.PI + 360) % 360;
    setLocation(d.id, { lat, lng, speed: r.speedKmh / 3.6, bearing: Math.round(bearing) }, 'route');
  }, 1000);
}
function pauseRoute(deviceId) {
  // 暫停: 只停計時器, 路線進度 (segIdx / segPos) 留著, 繼續時從同一點接著走。
  // 位置本身不動 (模擬程序停在最後一個座標), 點大花、滑金色花苗的時間就有了。
  const d = devices.get(deviceId);
  if (!d || !d.routeTimer || !d.route) return false;
  clearInterval(d.routeTimer); d.routeTimer = null; d.routePaused = true;
  return true;
}
function resumeRoute(deviceId) {
  const d = devices.get(deviceId);
  if (!d || !d.route || !d.routePaused) return false;
  d.routePaused = false;
  startRouteTimer(d);
  return true;
}

// ---- 地理編碼 ----
async function geocodeNominatim(q) {
  // Nominatim 對中文門牌號解析較弱 (例: 興大路145號常回空), 依序退化查詢:
  // 完整地址 -> 去掉門牌號 -> 只留路名, 並標註 fallback, 讓使用者確認
  const variants = [q];
  const noHouse = q.replace(/\d+號.*$/, '').replace(/\d+巷.*$/, '').trim();
  if (noHouse && noHouse !== q) variants.push(noHouse);
  const roadOnly = q.match(/(.+?[路街大道巷弄])/);
  if (roadOnly && !variants.includes(roadOnly[1])) variants.push(roadOnly[1]);
  for (const v of variants) {
    const url = `https://nominatim.openstreetmap.org/search?format=json&limit=5&addressdetails=1&accept-language=zh-TW&countrycodes=tw&q=${encodeURIComponent(v)}`;
    const r = await fetch(url, { headers: { 'User-Agent': 'virtual-location-prototype/0.1 (contact: local-dev)' } });
    if (!r.ok) throw new Error(`Nominatim ${r.status}`);
    const j = await r.json();
    if (j.length) return j.map((x) => ({
      lat: parseFloat(x.lat), lng: parseFloat(x.lon),
      formatted_address: x.display_name, place_id: String(x.place_id), provider: 'nominatim',
      fallback: v !== q ? `以「${v}」查詢 (Nominatim 不支援此門牌號精確解析)` : undefined,
    }));
  }
  return [];
}
async function geocodeGoogle(q) {
  const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(q)}&language=zh-TW&region=tw&key=${GOOGLE_API_KEY}`;
  const r = await fetch(url);
  const j = await r.json();
  if (j.status !== 'OK') throw new Error(`Google Geocoding: ${j.status} ${j.error_message || ''}`);
  return j.results.map((x) => ({
    lat: x.geometry.location.lat, lng: x.geometry.location.lng,
    formatted_address: x.formatted_address, place_id: x.place_id, provider: 'google',
  }));
}

// ---- REST API ----
app.get('/health', (req, res) => res.json({ ok: true, geocoder: GEOCODER, devices: devices.size, ts: Date.now() }));

app.get('/api/geocode', async (req, res) => {
  const q = (req.query.q || '').trim();
  if (!q) return res.status(400).json({ error: '缺少 q 參數, 例: /api/geocode?q=台中市南區興大路145號' });
  try {
    const provider = req.query.provider || GEOCODER;
    const results = provider === 'google' ? await geocodeGoogle(q) : await geocodeNominatim(q);
    if (!results.length) return res.json({ query: q, results: [], note: '找不到結果, 試試更完整的地址或地標' });
    res.json({ query: q, provider, results });
  } catch (e) { res.status(502).json({ error: String(e.message || e) }); }
});

app.get('/api/devices', (req, res) => res.json([...devices.values()].map(publicDevice)));
app.post('/api/devices', (req, res) => {
  const { id, type, name } = req.body || {};
  if (!id || !type) return res.status(400).json({ error: '需要 id 與 type (web / android / ios-bridge)' });
  // 已存在的裝置只更新名稱/類型, 絕對不要重建:
  // 中控台每次開頁面都會重送三台預設裝置, 重建會清掉真機的 socketId、
  // 目前座標和跑到一半的路線計時器, 路線就停不下來。
  const existing = devices.get(id);
  if (existing) {
    existing.type = type; existing.name = name || existing.name; existing.lastSeen = Date.now();
    broadcastDevices();
    return res.json(publicDevice(existing));
  }
  const d = { id, type, name: name || id, status: 'online', socketId: null, location: null, lastSeen: Date.now(), routeTimer: null, joystickTimer: null };
  devices.set(id, d); broadcastDevices();
  logEvent('device', `裝置註冊: ${d.name} (${type})`);
  res.status(201).json(publicDevice(d));
});
app.delete('/api/devices/:id', (req, res) => {
  const d = devices.get(req.params.id);
  if (!d) return res.status(404).json({ error: '裝置不存在' });
  stopRoute(req.params.id);
  stopJoystick(req.params.id);
  devices.delete(req.params.id);
  broadcastDevices();
  logEvent('device', `裝置已移除: ${d.name} (${d.type})`);
  res.json({ ok: true, id: req.params.id });
});
app.post('/api/devices/:id/location', (req, res) => {
  const { lat, lng, accuracy } = req.body || {};
  if (typeof lat !== 'number' || typeof lng !== 'number') return res.status(400).json({ error: '需要數字 lat / lng' });
  if (!devices.has(req.params.id)) return res.status(404).json({ error: '裝置不存在, 先 POST /api/devices 註冊' });
  // 瞬移就是要去新位置: 先停掉跑到一半的路線, 不然路線每秒推播會立刻把裝置拉回路線上,
  // 看起來就像路線「砍不掉」。
  if (stopRoute(req.params.id)) io.emit('route:stop', { deviceId: req.params.id });
  stopJoystick(req.params.id);
  const loc = setLocation(req.params.id, { lat, lng, accuracy });
  res.json({ deviceId: req.params.id, location: loc });
});
app.post('/api/devices/:id/location/clear', (req, res) => {
  const d = devices.get(req.params.id);
  if (!d) return res.status(404).json({ error: '裝置不存在' });
  if (stopRoute(req.params.id)) io.emit('route:stop', { deviceId: req.params.id });
  stopJoystick(req.params.id);
  d.location = null;
  io.emit('location:clear', { deviceId: req.params.id });
  logEvent('location', `${d.name} 已還原真實定位`);
  res.json({ ok: true });
});

// 路線模擬: 後端每秒插值推播, 讓 Android / iOS / 網頁端同步移動
app.post('/api/devices/:id/route', (req, res) => {
  const { waypoints, speedKmh = 30, loop = false } = req.body || {};
  const d = devices.get(req.params.id);
  if (!d) return res.status(404).json({ error: '裝置不存在' });
  if (!Array.isArray(waypoints) || waypoints.length < 2) return res.status(400).json({ error: 'waypoints 至少需要 2 個點 [{lat,lng}]' });
  stopRoute(req.params.id);
  stopJoystick(req.params.id);
  // 預先算每段距離 (公尺, Haversine)
  const R = 6371000, toRad = (x) => x * Math.PI / 180;
  const dist = (a, b) => { const dLat = toRad(b.lat - a.lat), dLng = toRad(b.lng - a.lng); const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
  const segs = []; for (let i = 0; i < waypoints.length - 1; i++) segs.push({ from: waypoints[i], to: waypoints[i + 1], d: dist(waypoints[i], waypoints[i + 1]) });
  // 路線狀態存在裝置上, 暫停/繼續靠它接著走
  d.route = { waypoints, speedKmh, loop, segs, segIdx: 0, segPos: 0, stepM: Math.max(1, (speedKmh * 1000) / 3600) };
  d.routePaused = false;
  io.emit('route:start', { deviceId: req.params.id, waypoints, speedKmh });
  startRouteTimer(d);
  res.json({ ok: true, deviceId: req.params.id, segments: segs.length, totalMeters: Math.round(segs.reduce((a, s) => a + s.d, 0)) });
});
app.post('/api/devices/:id/route/pause', (req, res) => {
  if (!devices.has(req.params.id)) return res.status(404).json({ error: '裝置不存在' });
  if (!pauseRoute(req.params.id)) return res.status(400).json({ error: '沒有正在跑的路線可暫停' });
  io.emit('route:pause', { deviceId: req.params.id }); res.json({ ok: true, paused: true });
});
app.post('/api/devices/:id/route/resume', (req, res) => {
  if (!devices.has(req.params.id)) return res.status(404).json({ error: '裝置不存在' });
  if (!resumeRoute(req.params.id)) return res.status(400).json({ error: '沒有暫停中的路線可繼續' });
  io.emit('route:resume', { deviceId: req.params.id }); res.json({ ok: true, paused: false });
});
app.post('/api/devices/:id/route/stop', (req, res) => { if (stopRoute(req.params.id)) io.emit('route:stop', { deviceId: req.params.id }); res.json({ ok: true }); });

// 虛擬搖桿: 中控台搖桿推著走, 放開就停。dx 向東、dy 向北 (-1..1), 幅度決定速度比例。
// 開始搖桿會先停掉路線 (跟瞬移一樣, 不然路線每秒推播會把裝置拉回去)。
app.post('/api/devices/:id/joystick', (req, res) => {
  const { dx, dy, speedKmh = 6 } = req.body || {};
  const d = devices.get(req.params.id);
  if (!d) return res.status(404).json({ error: '裝置不存在' });
  if (typeof dx !== 'number' || typeof dy !== 'number') return res.status(400).json({ error: '需要數字 dx / dy (-1..1, dx 向東, dy 向北)' });
  if (!d.location) return res.status(400).json({ error: '裝置還沒有位置, 先瞬移設定一個起點' });
  const mag = Math.min(1, Math.hypot(dx, dy));
  if (mag < 0.15) { stopJoystick(req.params.id); return res.json({ ok: true, stopped: true }); }
  if (stopRoute(req.params.id)) io.emit('route:stop', { deviceId: req.params.id });
  stopJoystick(req.params.id);
  d.joystick = { dx: dx / mag, dy: dy / mag, magnitude: mag, speedKmh };
  startJoystickTimer(d);
  io.emit('joystick:start', { deviceId: req.params.id });
  res.json({ ok: true, joystick: true });
});
app.post('/api/devices/:id/joystick/stop', (req, res) => {
  if (!devices.has(req.params.id)) return res.status(404).json({ error: '裝置不存在' });
  if (stopJoystick(req.params.id)) io.emit('joystick:stop', { deviceId: req.params.id });
  res.json({ ok: true });
});

app.get('/api/bookmarks', (req, res) => res.json(bookmarks));
app.post('/api/bookmarks', (req, res) => {
  const { name, address, lat, lng } = req.body || {};
  if (!name || typeof lat !== 'number' || typeof lng !== 'number') return res.status(400).json({ error: '需要 name, lat, lng' });
  const b = { id: `bm-${Date.now()}`, name, address: address || '', lat, lng };
  bookmarks.push(b); res.status(201).json(b);
});
app.get('/api/log', (req, res) => res.json(eventLog.slice(0, 50)));

// ---- WebSocket ----
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });
io.on('connection', (socket) => {
  socket.emit('devices:update', [...devices.values()].map(publicDevice));
  socket.on('register', ({ id, type, name }) => {
    if (!id) return;
    const d = devices.get(id) || { id, type: type || 'unknown', name: name || id, location: null, routeTimer: null };
    d.status = 'online'; d.socketId = socket.id; d.lastSeen = Date.now(); d.type = type || d.type; d.name = name || d.name;
    devices.set(id, d); socket.data.deviceId = id; broadcastDevices();
    logEvent('device', `裝置上線: ${d.name} (${d.type})`);
  });
  socket.on('location:update', ({ deviceId, lat, lng, accuracy }) => {
    if (deviceId && typeof lat === 'number' && typeof lng === 'number') setLocation(deviceId, { lat, lng, accuracy });
  });
  socket.on('location:clear', ({ deviceId }) => {
    const d = devices.get(deviceId); if (d) { stopRoute(deviceId); stopJoystick(deviceId); d.location = null; io.emit('location:clear', { deviceId }); }
  });
  socket.on('disconnect', () => {
    const id = socket.data.deviceId;
    if (id && devices.get(id)) { devices.get(id).status = 'offline'; devices.get(id).socketId = null; broadcastDevices(); }
  });
});

server.listen(PORT, () => {
  console.log(`虛擬定位中控後端已啟動: http://localhost:${PORT}`);
  console.log(`Geocoder: ${GEOCODER}${GOOGLE_API_KEY ? ' (Google)' : ' (Nominatim 免費版)'}`);
  console.log('測試: curl "http://localhost:3000/api/geocode?q=台中市南區興大路145號"');
});
