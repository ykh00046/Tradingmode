// =============================================================================
// loader.js — fetch instruments from the backend and reshape them to the
// `buildInstrument()` shape that data.js / app.jsx already use.
//
// Loaded after data.js so we can reuse `window.MarketData.helpers` for
// per-bar trend / cross / EMA computations that the backend does not return.
//
// Public:
//   window.loader.loadAllInstruments(universe, opts) → Promise<DATA>
//   window.loader.loadInstrument(meta, opts)         → Promise<instrument>
// =============================================================================

(function () {
  'use strict';

  // BTC/USDT → BTCUSDT (frontend uses the slash form for display)
  function symbolToBackend(display) {
    return display.replace('/', '');
  }

  // Frontend uses 'kr' / 'crypto'; backend uses 'kr_stock' / 'crypto'.
  function marketToBackend(m) {
    return m === 'kr' ? 'kr_stock' : 'crypto';
  }

  // Korean labels for signal kinds (matches data.js BUY_KINDS / SELL_KINDS).
  var KIND_LABEL = {
    golden_cross:    '골든크로스',
    death_cross:     '데드크로스',
    rsi_oversold:    'RSI 과매도',
    rsi_overbought:  'RSI 과매수',
    rsi_bull_div:    'RSI 강세 다이버전스',
    rsi_bear_div:    'RSI 약세 다이버전스',
    macd_bull_cross: 'MACD 상향교차',
    macd_bear_cross: 'MACD 하향교차',
  };

  // Pull a column from the indicators dict, returning a length-padded array
  // so consumer code can index by candle position without bounds checks.
  function getColumn(indDict, key, length) {
    var arr = indDict[key];
    if (!arr) {
      return new Array(length).fill(null);
    }
    if (arr.length === length) return arr;
    if (arr.length < length) {
      // Front-pad with nulls so indices stay aligned with candles
      var pad = new Array(length - arr.length).fill(null);
      return pad.concat(arr);
    }
    return arr.slice(0, length);
  }

  // Backend → frontend indicator object
  function buildInd(indDict, candleCount, closes) {
    var ind = {
      ma5:   getColumn(indDict, 'SMA_5',   candleCount),
      ma20:  getColumn(indDict, 'SMA_20',  candleCount),
      ma60:  getColumn(indDict, 'SMA_60',  candleCount),
      ma120: getColumn(indDict, 'SMA_120', candleCount),
      ema12: new Array(candleCount).fill(null),
      rsi14: getColumn(indDict, 'RSI_14', candleCount),
      macd: {
        line:   getColumn(indDict, 'MACD_12_26_9',  candleCount),
        signal: getColumn(indDict, 'MACDs_12_26_9', candleCount),
        hist:   getColumn(indDict, 'MACDh_12_26_9', candleCount),
      },
      bb: {
        mid: getColumn(indDict, 'BBM_20_2.0_2.0', candleCount),
        up:  getColumn(indDict, 'BBU_20_2.0_2.0', candleCount),
        lo:  getColumn(indDict, 'BBL_20_2.0_2.0', candleCount),
      },
      // RSI Price Band — RSI 역산 가격 밴드 (v0.6)
      rpb: {
        up: {
          70: getColumn(indDict, 'RPB_UP_70', candleCount),
          75: getColumn(indDict, 'RPB_UP_75', candleCount),
          80: getColumn(indDict, 'RPB_UP_80', candleCount),
        },
        dn: {
          30: getColumn(indDict, 'RPB_DN_30', candleCount),
          25: getColumn(indDict, 'RPB_DN_25', candleCount),
          20: getColumn(indDict, 'RPB_DN_20', candleCount),
        },
        bars: {
          up: {
            70: getColumn(indDict, 'RPB_UP_70_BARS', candleCount),
            75: getColumn(indDict, 'RPB_UP_75_BARS', candleCount),
            80: getColumn(indDict, 'RPB_UP_80_BARS', candleCount),
          },
          dn: {
            30: getColumn(indDict, 'RPB_DN_30_BARS', candleCount),
            25: getColumn(indDict, 'RPB_DN_25_BARS', candleCount),
            20: getColumn(indDict, 'RPB_DN_20_BARS', candleCount),
          },
        },
      },
    };

    // Compute EMA12 on the frontend — backend uses it internally for MACD only.
    var helpers = window.MarketData && window.MarketData.helpers;
    if (helpers && typeof helpers.ema === 'function') {
      ind.ema12 = helpers.ema(closes, 12);
    }
    return ind;
  }

  // Backend signals (timestamps in ms) → frontend signals (with `i` index)
  function backendSignalsToFrontend(signals, candles) {
    var tToI = new Map();
    candles.forEach(function (c, i) { tToI.set(c.t, i); });
    var out = [];
    for (var k = 0; k < signals.length; k++) {
      var s = signals[k];
      var i = tToI.get(s.timestamp);
      if (i === undefined) continue;     // stale signal (out of fetched range)
      out.push({
        i: i,
        t: s.timestamp,
        kind: s.kind,
        label: KIND_LABEL[s.kind] || s.kind,
        strength: s.strength,
      });
    }
    out.sort(function (a, b) { return a.i - b.i; });
    return out;
  }

  // /api/backtest result → frontend {trades, equity, stats}
  function backendBacktestToFrontend(bt) {
    var trades = (bt.trades || []).map(function (t) {
      // backtesting.py uses CamelCase columns; if our converters renamed them
      // we still try both shapes.
      return {
        entryT: t.EntryTime  || t.entry_t || null,
        exitT:  t.ExitTime   || t.exit_t  || null,
        entryP: t.EntryPrice || t.entry_price || 0,
        exitP:  t.ExitPrice  || t.exit_price  || 0,
        ret:    typeof t.ReturnPct === 'number' ? t.ReturnPct / 100 : (t.ret || 0),
      };
    });
    var equity = (bt.equity_curve || []).map(function (p) {
      // Frontend chart expects {t, eq} where eq is normalised to start at 1.
      return { t: p.t, eq: p.equity };
    });
    // Re-normalise so first eq = 1 (frontend renderer expects this).
    if (equity.length > 0 && equity[0].eq && equity[0].eq !== 1) {
      var base = equity[0].eq;
      equity = equity.map(function (p) { return { t: p.t, eq: p.eq / base }; });
    }
    return {
      trades: trades,
      equity: equity,
      stats: {
        totalReturn: (bt.total_return || 0) / 100,
        winRate:     (bt.win_rate || 0) / 100,
        maxDD:       -Math.abs(bt.max_drawdown || 0) / 100,
        trades:      bt.num_trades || 0,
        avgRet:      bt.num_trades > 0 ? (bt.total_return || 0) / bt.num_trades / 100 : 0,
        sharpe:      bt.sharpe_ratio || 0,
      },
    };
  }

  function emptyBacktest(candles) {
    var equity = (candles && candles.length)
      ? candles.map(function (c) { return { t: c.t, eq: 1 }; })
      : [{ t: 0, eq: 1 }];
    return {
      trades: [],
      equity: equity,
      stats: {
        totalReturn: 0,
        winRate: 0,
        maxDD: 0,
        trades: 0,
        avgRet: 0,
        sharpe: 0,
      },
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public: loadInstrument
  // ─────────────────────────────────────────────────────────────────────────
  async function loadInstrument(meta, opts) {
    opts = opts || {};
    var lookbackDays = opts.lookbackDays || 365;
    var range = window.api.dateRange(lookbackDays);
    var params = {
      market:   marketToBackend(meta.market),
      symbol:   symbolToBackend(meta.symbol),
      interval: '1d',
      start:    range.start,
      end:      range.end,
    };

    // Parallel fan-out — /api/indicators already includes the OHLCV candles,
    // so we don't need to call /api/ohlcv separately.
    var indP   = window.api.indicators(params, { signal: opts.signal });
    var sigP   = window.api.signals(params, { signal: opts.signal });
    var btReq  = Object.assign({}, params, {
      strategy:   'ma_cross',
      cash:       1_000_000,
      commission: 0.0005,
    });
    var btP    = window.api.backtest(btReq, { signal: opts.signal, timeout: 30000 })
      .then(
        function (value) { return { ok: true, value: value }; },
        function (error) { return { ok: false, error: error }; }
      );

    var results = await Promise.all([indP, sigP]);
    var indResp  = results[0];
    var sigResp  = results[1];

    var candles = indResp.candles || [];
    var closes  = candles.map(function (c) { return c.c; });
    var ind     = buildInd(indResp.indicators || {}, candles.length, closes);
    var helpers = window.MarketData && window.MarketData.helpers;

    // Per-bar trend (backend only returns the latest classification).
    var trend = helpers && helpers.classifyTrend
      ? helpers.classifyTrend(closes, ind.ma20, ind.ma60, ind.ma120)
      : new Array(candles.length).fill('side');

    // MA crosses — needed by chart markers + simple backtest fallback.
    var crosses = helpers && helpers.findCrosses
      ? helpers.findCrosses(ind.ma20, ind.ma60)
      : [];

    var signals = backendSignalsToFrontend(sigResp.signals || [], candles);
    var bt = emptyBacktest(candles);
    var backtestStatus = 'unavailable';
    var backtestError = null;
    var btResult = await btP;
    if (btResult.ok) {
      bt = backendBacktestToFrontend(btResult.value);
      backtestStatus = 'ok';
    } else {
      var e = btResult.error;
      backtestError = e && (e.code || e.message) || 'backtest unavailable';
      console.warn('[loader] backtest unavailable for', meta.symbol, backtestError);
    }

    return {
      meta:    meta,
      candles: candles,
      ind:     ind,
      trend:   trend,
      signals: signals,
      crosses: crosses,
      trades:  bt.trades,
      equity:  bt.equity,
      stats:   bt.stats,
      backtestStatus: backtestStatus,
      backtestError: backtestError,
    };
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Public: loadAllInstruments
  //
  // Fetches every symbol in the universe in batches (default concurrency=3 to
  // stay well under Binance/pykrx rate limits during cold-cache loads).
  // Symbols that fail are silently dropped — the existing window.MarketData.DATA
  // (synthetic) entry is kept as a fallback so the UI never shows a missing tile.
  // ─────────────────────────────────────────────────────────────────────────
  async function loadAllInstruments(universe, opts) {
    opts = opts || {};
    var onProgress  = typeof opts.onProgress === 'function' ? opts.onProgress : function () {};
    var concurrency = opts.concurrency || 3;
    var data        = {};
    var done        = 0;

    onProgress({ done: 0, total: universe.length, current: null });

    for (var i = 0; i < universe.length; i += concurrency) {
      var batch = universe.slice(i, i + concurrency);
      await Promise.all(batch.map(async function (meta) {
        try {
          var inst = await loadInstrument(meta, { signal: opts.signal });
          data[meta.symbol] = inst;
        } catch (e) {
          console.warn('[loader] failed for', meta.symbol, e && (e.code || e.message));
          // Fall back to whatever data.js already populated.
          var fallback = window.MarketData && window.MarketData.DATA && window.MarketData.DATA[meta.symbol];
          if (fallback) data[meta.symbol] = fallback;
        }
        done += 1;
        onProgress({ done: done, total: universe.length, current: meta.symbol });
      }));
    }

    // Swap the global DATA so existing JSX components transparently see real data.
    if (window.MarketData) {
      window.MarketData.DATA = data;
    }
    return data;
  }

  window.loader = {
    loadInstrument:     loadInstrument,
    loadAllInstruments: loadAllInstruments,
    symbolToBackend:    symbolToBackend,
    marketToBackend:    marketToBackend,
    KIND_LABEL:         KIND_LABEL,
  };
})();
