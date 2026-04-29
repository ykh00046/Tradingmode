// =============================================================================
// api.js — single entry point for every backend call
// =============================================================================
//
// Loaded from index.html before data.js so other scripts can `window.api.*`.
//
// Backend lives at `window.API_BASE_URL` (default: http://localhost:8000) — set
// in index.html via:
//   <script>window.API_BASE_URL = 'http://localhost:8000'</script>
//
// Every method accepts an optional second arg `{ signal, timeout }` — pass an
// AbortSignal when you need to cancel in-flight requests (race conditions on
// fast tab switches), or override the default 15s timeout.
//
// All errors surface as `window.ApiError` instances with:
//   - code:    matches backend error code (or 'TIMEOUT' / 'NETWORK' / 'UNKNOWN')
//   - message: human-readable
//   - status:  HTTP status (0 for network/timeout)
//   - details: extra info from the backend (rate-limit window, validation errors)
//
// See backend §4.5 of the Design doc for the full endpoint list.
// =============================================================================

(function () {
  'use strict';

  var API_BASE = (window.API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
  var DEFAULT_TIMEOUT = 15000;

  // --- ApiError -------------------------------------------------------------
  function ApiError(code, message, status, details) {
    var err = new Error(message || code || 'API error');
    err.name = 'ApiError';
    err.code = code || 'UNKNOWN';
    err.status = typeof status === 'number' ? status : 0;
    err.details = details || {};
    return err;
  }

  // --- Internal helpers -----------------------------------------------------
  async function _check(res) {
    if (!res.ok) {
      var body = null;
      try { body = await res.json(); } catch (_) { /* non-JSON error body */ }
      var info = (body && body.error) || {};
      throw ApiError(
        info.code || 'UNKNOWN',
        info.message || res.statusText || ('HTTP ' + res.status),
        res.status,
        info.details || {}
      );
    }
    return res.json();
  }

  function _withTimeout(externalSignal, timeoutMs) {
    var ctl = new AbortController();
    var timer = setTimeout(function () {
      ctl.abort(ApiError('TIMEOUT', 'request timed out after ' + timeoutMs + 'ms', 0));
    }, timeoutMs);
    if (externalSignal) {
      if (externalSignal.aborted) {
        ctl.abort(externalSignal.reason);
      } else {
        externalSignal.addEventListener('abort', function () {
          ctl.abort(externalSignal.reason);
        }, { once: true });
      }
    }
    return {
      signal: ctl.signal,
      clear: function () { clearTimeout(timer); }
    };
  }

  function _buildUrl(path, params) {
    var url = new URL(API_BASE + path);
    if (params) {
      Object.keys(params).forEach(function (k) {
        var v = params[k];
        if (v === undefined || v === null) return;
        url.searchParams.set(k, String(v));
      });
    }
    return url;
  }

  async function _do(method, path, options, body, opts) {
    opts = opts || {};
    var timeout = opts.timeout || DEFAULT_TIMEOUT;
    var combined = _withTimeout(opts.signal, timeout);

    try {
      var init = {
        method: method,
        headers: Object.assign({ 'Accept': 'application/json' }, options.headers || {}),
        signal: combined.signal,
      };
      if (body !== undefined && body !== null) {
        init.headers['Content-Type'] = 'application/json';
        init.body = JSON.stringify(body);
      }
      var res = await fetch(options.url, init);
      return await _check(res);
    } catch (e) {
      // Normalize fetch errors → ApiError so callers only handle one shape.
      if (e && e.name === 'ApiError') throw e;
      if (e && (e.name === 'AbortError' || e.code === 'TIMEOUT')) {
        // Pass through abort/timeout as-is (the timeout abort already produced
        // a proper ApiError; user-initiated aborts keep the standard AbortError
        // so callers can distinguish "user navigated away" vs "request failed").
        throw e;
      }
      throw ApiError(
        'NETWORK',
        e && e.message ? e.message : 'network error',
        0,
        { type: e && e.name }
      );
    } finally {
      combined.clear();
    }
  }

  function apiGet(path, params, opts) {
    return _do('GET', path, { url: _buildUrl(path, params) }, null, opts);
  }

  function apiPost(path, body, opts) {
    return _do('POST', path, { url: _buildUrl(path, null) }, body, opts);
  }

  // --- Public API surface ---------------------------------------------------
  window.api = {
    base: API_BASE,
    health:           function (opt)            { return apiGet('/api/health', null, opt); },
    ohlcv:            function (params, opt)    { return apiGet('/api/ohlcv', params, opt); },
    indicators:       function (params, opt)    { return apiGet('/api/indicators', params, opt); },
    signals:          function (params, opt)    { return apiGet('/api/signals', params, opt); },
    trend:            function (params, opt)    { return apiGet('/api/trend', params, opt); },
    marketSnapshot:   function (opt)            { return apiGet('/api/market/snapshot', null, opt); },
    aiExplain:        function (body, opt)      { return apiPost('/api/ai/explain', body, opt); },
    portfolio:        function (body, opt)      { return apiPost('/api/portfolio', body, opt); },
    backtest:         function (body, opt)      { return apiPost('/api/backtest', body, opt); },
  };

  window.ApiError = ApiError;

  // --- Date helpers (frontend uses unix-ms throughout) ----------------------
  // Keep here so callers don't have to remember the conversion convention.
  window.api.dateRange = function (lookbackDays) {
    var end = Date.now();
    var start = end - lookbackDays * 24 * 60 * 60 * 1000;
    return { start: start, end: end };
  };

  // --- Demo mode flag -------------------------------------------------------
  // ?demo=1 → bypass backend, use synthetic data.js fallback (data.js loads
  // unconditionally and other modules check this flag before calling api.*).
  var qs = new URLSearchParams(window.location.search);
  window.DEMO_MODE = qs.get('demo') === '1';

  console.log(
    '[api.js] base=' + API_BASE +
    ', demo=' + window.DEMO_MODE +
    (window.DEMO_MODE ? ' — backend disabled, using synthetic data' : '')
  );
})();
