// Tradingmode localStorage helper (Design v0.3 §4.1)
// Plain JS IIFE — exposes window.tmStorage. Loaded BEFORE any .jsx component.
(function () {
  const PREFIX = 'tradingmode-';

  function get(key, fallback) {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (raw === null) return fallback;
      return JSON.parse(raw);
    } catch (e) {
      console.warn('[tmStorage] parse failed for', key, e);
      return fallback;
    }
  }

  function set(key, value) {
    try {
      localStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch (e) {
      console.warn('[tmStorage] set failed for', key, e);
    }
  }

  function remove(key) {
    try { localStorage.removeItem(PREFIX + key); } catch (_) {}
  }

  window.tmStorage = { get, set, remove, PREFIX };
})();
