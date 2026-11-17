// content.js — MAIN 世界, document_start 執行, 在網頁自己的程式之前
// 先把 navigator.geolocation 蓋掉。座標由 bridge.js 用 postMessage 傳進來。
// 後端沒指定座標 (target 為 null) 時就走回真實定位, 不擋路。
(function () {
  let target = null;
  const watchTimers = new Map();

  const origGet = navigator.geolocation.getCurrentPosition.bind(navigator.geolocation);
  const origWatch = navigator.geolocation.watchPosition.bind(navigator.geolocation);
  const origClear = navigator.geolocation.clearWatch.bind(navigator.geolocation);

  function fakePosition() {
    return {
      coords: {
        latitude: target.lat,
        longitude: target.lng,
        accuracy: 5,
        altitude: null,
        altitudeAccuracy: null,
        heading: null,
        speed: null,
      },
      timestamp: Date.now(),
    };
  }

  navigator.geolocation.getCurrentPosition = function (success, error, options) {
    if (target && success) {
      setTimeout(() => success(fakePosition()), 0);
      return;
    }
    return origGet(success, error, options);
  };

  navigator.geolocation.watchPosition = function (success, error, options) {
    if (target && success) {
      success(fakePosition());
      const id = Math.floor(Math.random() * 1e9);
      watchTimers.set(id, setInterval(() => {
        if (target) success(fakePosition());
      }, 2000));
      return id;
    }
    return origWatch(success, error, options);
  };

  navigator.geolocation.clearWatch = function (id) {
    if (watchTimers.has(id)) {
      clearInterval(watchTimers.get(id));
      watchTimers.delete(id);
      return;
    }
    return origClear(id);
  };

  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.type !== "VL_TARGET") return;
    target = e.data.target;
  });
})();
