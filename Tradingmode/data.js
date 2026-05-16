// Synthetic OHLCV data generators + indicator calculations
// All values are deterministic (seeded) so the prototype looks the same on reload.

(function () {
  function mulberry32(seed) {
    return function () {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = seed;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Generate a believable OHLCV series given a starting price, volatility, drift
  function genOHLCV({ seed, n, start, vol, drift, volBase = 1e6, baseTime = null, intervalMs = 24 * 3600 * 1000 }) {
    const rnd = mulberry32(seed);
    const series = [];
    let price = start;
    const now = baseTime ?? Date.now();
    for (let i = 0; i < n; i++) {
      const t = now - (n - 1 - i) * intervalMs;
      // Random walk with regimes — produce trending segments + sideways
      const regime = Math.sin(i / 22) + Math.cos(i / 9) * 0.6; // smooth regime signal
      const r = (rnd() - 0.5) * 2; // -1..1
      const mu = drift * (0.6 + regime * 0.4);
      const sig = vol * (0.7 + Math.abs(regime) * 0.6);
      const ret = mu + sig * r;
      const open = price;
      const close = Math.max(0.01, open * (1 + ret));
      const hi = Math.max(open, close) * (1 + Math.abs(rnd() * sig * 0.6));
      const lo = Math.min(open, close) * (1 - Math.abs(rnd() * sig * 0.6));
      const v = volBase * (0.5 + rnd() * 1.5) * (1 + Math.abs(ret) * 6);
      series.push({ t, o: open, h: hi, l: lo, c: close, v });
      price = close;
    }
    return series;
  }

  // ── Indicators ──────────────────────────────────────────────
  function sma(arr, p) {
    const out = new Array(arr.length).fill(null);
    let sum = 0;
    for (let i = 0; i < arr.length; i++) {
      sum += arr[i];
      if (i >= p) sum -= arr[i - p];
      if (i >= p - 1) out[i] = sum / p;
    }
    return out;
  }
  function ema(arr, p) {
    const out = new Array(arr.length).fill(null);
    const k = 2 / (p + 1);
    let prev = null;
    for (let i = 0; i < arr.length; i++) {
      if (i < p - 1) continue;
      if (prev === null) {
        let s = 0;
        for (let j = i - p + 1; j <= i; j++) s += arr[j];
        prev = s / p;
      } else {
        prev = arr[i] * k + prev * (1 - k);
      }
      out[i] = prev;
    }
    return out;
  }
  function rsi(closes, p = 14) {
    const out = new Array(closes.length).fill(null);
    let g = 0,
      l = 0;
    for (let i = 1; i < closes.length; i++) {
      const ch = closes[i] - closes[i - 1];
      const up = Math.max(0, ch),
        dn = Math.max(0, -ch);
      if (i <= p) {
        g += up;
        l += dn;
        if (i === p) {
          g /= p;
          l /= p;
          out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
        }
      } else {
        g = (g * (p - 1) + up) / p;
        l = (l * (p - 1) + dn) / p;
        out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
      }
    }
    return out;
  }
  function macd(closes, fast = 12, slow = 26, signal = 9) {
    const ef = ema(closes, fast);
    const es = ema(closes, slow);
    const line = closes.map((_, i) => (ef[i] != null && es[i] != null ? ef[i] - es[i] : null));
    // Signal = EMA of the MACD line, seeded from the first bar the line
    // actually exists. Zero-padding the null head (the old `?? 0`) dragged the
    // EMA seed toward 0 and biased the signal / histogram for ~25 early bars.
    const firstValid = line.findIndex((v) => v != null);
    const sigArr = new Array(line.length).fill(null);
    if (firstValid >= 0) {
      const sigCompact = ema(line.slice(firstValid), signal);
      for (let i = 0; i < sigCompact.length; i++) sigArr[firstValid + i] = sigCompact[i];
    }
    const hist = line.map((v, i) => (v != null && sigArr[i] != null ? v - sigArr[i] : null));
    return { line, signal: sigArr, hist };
  }
  function bbands(closes, p = 20, mult = 2) {
    const mid = sma(closes, p);
    const up = new Array(closes.length).fill(null);
    const lo = new Array(closes.length).fill(null);
    for (let i = p - 1; i < closes.length; i++) {
      let s = 0;
      for (let j = i - p + 1; j <= i; j++) s += (closes[j] - mid[i]) ** 2;
      const sd = Math.sqrt(s / p);
      up[i] = mid[i] + mult * sd;
      lo[i] = mid[i] - mult * sd;
    }
    return { mid, up, lo };
  }

  // Wilder's smoothed moving average (RMA) — SMA-seeded, alpha = 1/length.
  // Matches the smoothing used by rsi() above. Nulls treated as 0.
  function wilderRma(arr, length) {
    const out = new Array(arr.length).fill(null);
    let prev = null;
    for (let i = 0; i < arr.length; i++) {
      const x = arr[i] == null ? 0 : arr[i];
      if (i < length - 1) continue;
      if (prev === null) {
        let s = 0;
        for (let j = i - length + 1; j <= i; j++) s += arr[j] == null ? 0 : arr[j];
        prev = s / length;
      } else {
        prev = (prev * (length - 1) + x) / length;
      }
      out[i] = prev;
    }
    return out;
  }

  // RSI Price Band — Wilder RMA 역산: "다음 봉이 X로 마감하면 RSI=N" 가격.
  // 백엔드 add_rpb 포팅 (데모 모드용). 양방향 산출, ATR×mult 거리 필터 + RS Cap.
  // 반환 형태는 loader.js buildInd 의 nested rpb 와 동일.
  function rpb(candles, opts) {
    opts = opts || {};
    const upper = opts.upper || [70, 75, 80];
    const lower = opts.lower || [30, 25, 20];
    const rsiLen = opts.rsiLen || 14;
    const atrLen = opts.atrLen || 14;
    const atrMult = opts.atrMult || 5;
    const rsCap = (opts.rsCapRsi || 70) / (100 - (opts.rsCapRsi || 70));
    const n = rsiLen - 1;                       // Pine 원전 표기
    const N = candles.length;
    const close = candles.map((c) => c.c);

    const gain = new Array(N).fill(0), loss = new Array(N).fill(0);
    for (let i = 1; i < N; i++) {
      const ch = close[i] - close[i - 1];
      gain[i] = Math.max(0, ch);
      loss[i] = Math.max(0, -ch);
    }
    const avgGain = wilderRma(gain, rsiLen);
    const avgLoss = wilderRma(loss, rsiLen);

    const tr = new Array(N).fill(null);
    for (let i = 0; i < N; i++) {
      const c = candles[i];
      tr[i] = i === 0
        ? c.h - c.l
        : Math.max(c.h - c.l, Math.abs(c.h - close[i - 1]), Math.abs(c.l - close[i - 1]));
    }
    const atr = wilderRma(tr, atrLen);

    function mkBand(isUp, rsiT) {
      const rs = rsiT / (100 - rsiT);
      const price = new Array(N).fill(null);
      const bars = new Array(N).fill(null);
      for (let i = 0; i < N; i++) {
        const g = avgGain[i], l = avgLoss[i], a = atr[i];
        if (g == null || l == null || a == null) continue;
        const limit = a * atrMult;
        let p = null;
        if (isUp) {
          const x = n * (rs * l - g);
          const cand = close[i] + x;
          if (x > 0 && l > 0 && cand - close[i] <= limit) p = cand;
        } else {
          const gCap = Math.min(g, rsCap * l);
          const y = n * (gCap / rs - l);
          const cand = close[i] - y;
          if (gCap > 0 && y > 0 && cand > 0 && close[i] - cand <= limit) p = cand;
        }
        price[i] = p;
        bars[i] = p != null && a > 0 ? (p - close[i]) / a : null;
      }
      return { price, bars };
    }

    const up = {}, dn = {}, barsUp = {}, barsDn = {};
    upper.forEach((t) => { const b = mkBand(true, t); up[t] = b.price; barsUp[t] = b.bars; });
    lower.forEach((t) => { const b = mkBand(false, t); dn[t] = b.price; barsDn[t] = b.bars; });
    return { up, dn, bars: { up: barsUp, dn: barsDn } };
  }

  // Trend classification: ADX-ish using MA arrangement and slope
  function classifyTrend(closes, ma20, ma60, ma120) {
    const out = new Array(closes.length).fill('side');
    for (let i = 0; i < closes.length; i++) {
      if (ma20[i] == null || ma60[i] == null || ma120[i] == null) continue;
      const up = ma20[i] > ma60[i] && ma60[i] > ma120[i];
      const dn = ma20[i] < ma60[i] && ma60[i] < ma120[i];
      const slope = i > 5 && ma20[i - 5] != null ? (ma20[i] - ma20[i - 5]) / ma20[i - 5] : 0;
      if (up && slope > 0.002) out[i] = 'up';
      else if (dn && slope < -0.002) out[i] = 'down';
      else out[i] = 'side';
    }
    return out;
  }

  // Detect crosses between two MA arrays
  function findCrosses(a, b) {
    const out = [];
    for (let i = 1; i < a.length; i++) {
      if (a[i - 1] == null || b[i - 1] == null || a[i] == null || b[i] == null) continue;
      if (a[i - 1] <= b[i - 1] && a[i] > b[i]) out.push({ i, type: 'golden_cross' });
      else if (a[i - 1] >= b[i - 1] && a[i] < b[i]) out.push({ i, type: 'death_cross' });
    }
    return out;
  }

  // Build a full instrument bundle (candles + indicators + signals + backtest)
  function buildInstrument(meta) {
    const candles = genOHLCV(meta.gen);
    const closes = candles.map((c) => c.c);
    const ma20 = sma(closes, 20);
    const ma60 = sma(closes, 60);
    const ma120 = sma(closes, 120);
    const rsi14 = rsi(closes, 14);
    const md = macd(closes);
    const bb = bbands(closes, 20, 2);
    const rpbData = rpb(candles);
    const trend = classifyTrend(closes, ma20, ma60, ma120);
    const crosses = findCrosses(ma20, ma60);

    // Signals: golden_cross/death_cross + RSI extremes + MACD crosses + RSI divergence
    const signals = [];
    crosses.forEach((c) => signals.push({ i: c.i, t: candles[c.i].t, kind: c.type, label: c.type === 'golden_cross' ? '골든크로스' : '데드크로스', strength: 0.7 + Math.random() * 0.3 }));
    for (let i = 1; i < rsi14.length; i++) {
      if (rsi14[i - 1] != null && rsi14[i] != null) {
        if (rsi14[i - 1] >= 30 && rsi14[i] < 30) signals.push({ i, t: candles[i].t, kind: 'rsi_oversold', label: 'RSI 과매도', strength: 0.6 });
        if (rsi14[i - 1] <= 70 && rsi14[i] > 70) signals.push({ i, t: candles[i].t, kind: 'rsi_overbought', label: 'RSI 과매수', strength: 0.6 });
      }
    }
    // MACD crosses
    for (let i = 1; i < md.line.length; i++) {
      const pl = md.line[i - 1], ps = md.signal[i - 1], cl = md.line[i], cs = md.signal[i];
      if (pl == null || ps == null || cl == null || cs == null) continue;
      if (pl <= ps && cl > cs) signals.push({ i, t: candles[i].t, kind: 'macd_bull_cross', label: 'MACD 상향교차', strength: 0.65 });
      else if (pl >= ps && cl < cs) signals.push({ i, t: candles[i].t, kind: 'macd_bear_cross', label: 'MACD 하향교차', strength: 0.65 });
    }
    // RSI divergence (simplified: window of 20, find local lows/highs)
    const lookback = 20;
    for (let i = lookback * 2; i < closes.length; i++) {
      const w1Start = i - lookback * 2, w1End = i - lookback, w2Start = i - lookback, w2End = i;
      let w1LowI = w1Start, w2LowI = w2Start, w1HighI = w1Start, w2HighI = w2Start;
      for (let j = w1Start; j < w1End; j++) {
        if (closes[j] < closes[w1LowI]) w1LowI = j;
        if (closes[j] > closes[w1HighI]) w1HighI = j;
      }
      for (let j = w2Start; j < w2End; j++) {
        if (closes[j] < closes[w2LowI]) w2LowI = j;
        if (closes[j] > closes[w2HighI]) w2HighI = j;
      }
      if (rsi14[w1LowI] != null && rsi14[w2LowI] != null && closes[w2LowI] < closes[w1LowI] && rsi14[w2LowI] > rsi14[w1LowI] + 4) {
        if (!signals.some((s) => s.i === w2LowI && s.kind === 'rsi_bull_div')) signals.push({ i: w2LowI, t: candles[w2LowI].t, kind: 'rsi_bull_div', label: 'RSI 강세 다이버전스', strength: 0.8 });
      }
      if (rsi14[w1HighI] != null && rsi14[w2HighI] != null && closes[w2HighI] > closes[w1HighI] && rsi14[w2HighI] < rsi14[w1HighI] - 4) {
        if (!signals.some((s) => s.i === w2HighI && s.kind === 'rsi_bear_div')) signals.push({ i: w2HighI, t: candles[w2HighI].t, kind: 'rsi_bear_div', label: 'RSI 약세 다이버전스', strength: 0.8 });
      }
    }
    signals.sort((a, b) => a.i - b.i);

    // Simple backtest: enter long on golden cross, exit on dead cross
    const trades = [];
    let openTrade = null;
    crosses.forEach((c) => {
      if (c.type === 'golden_cross' && !openTrade) {
        openTrade = { entryI: c.i, entryT: candles[c.i].t, entryP: candles[c.i].c };
      } else if (c.type === 'death_cross' && openTrade) {
        const exitP = candles[c.i].c;
        const ret = (exitP - openTrade.entryP) / openTrade.entryP;
        trades.push({ ...openTrade, exitI: c.i, exitT: candles[c.i].t, exitP, ret, hold: c.i - openTrade.entryI });
        openTrade = null;
      }
    });
    // Close last
    if (openTrade) {
      const last = candles[candles.length - 1];
      const ret = (last.c - openTrade.entryP) / openTrade.entryP;
      trades.push({ ...openTrade, exitI: candles.length - 1, exitT: last.t, exitP: last.c, ret, hold: candles.length - 1 - openTrade.entryI, open: true });
    }

    // Equity curve
    let equity = 1;
    const equityCurve = candles.map((c) => ({ t: c.t, eq: 1 }));
    let peak = 1,
      maxDD = 0;
    let curEntry = null;
    let tIdx = 0;
    for (let i = 0; i < candles.length; i++) {
      if (curEntry == null && tIdx < trades.length && trades[tIdx].entryI === i) {
        curEntry = trades[tIdx].entryP;
      }
      if (curEntry != null && tIdx < trades.length && trades[tIdx].exitI === i) {
        equity *= candles[i].c / curEntry;
        curEntry = null;
        tIdx++;
      }
      const eq = curEntry != null ? equity * (candles[i].c / curEntry) : equity;
      equityCurve[i] = { t: candles[i].t, eq };
      peak = Math.max(peak, eq);
      maxDD = Math.min(maxDD, (eq - peak) / peak);
    }

    const wins = trades.filter((t) => t.ret > 0);
    const totalRet = equityCurve[equityCurve.length - 1].eq - 1;
    const stats = {
      totalReturn: totalRet,
      winRate: trades.length ? wins.length / trades.length : 0,
      maxDD,
      trades: trades.length,
      avgRet: trades.length ? trades.reduce((a, b) => a + b.ret, 0) / trades.length : 0,
      sharpe: estimateSharpe(equityCurve),
    };

    return { meta, candles, ind: { ma20, ma60, ma120, rsi14, macd: md, bb, rpb: rpbData }, trend, signals, crosses, trades, equity: equityCurve, stats };
  }

  function estimateSharpe(eq) {
    const rets = [];
    for (let i = 1; i < eq.length; i++) rets.push((eq[i].eq - eq[i - 1].eq) / eq[i - 1].eq);
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length);
    if (sd === 0) return 0;
    return (mean / sd) * Math.sqrt(252);
  }

  // ── Universe ────────────────────────────────────────────────
  const N = 240;
  const day = 24 * 3600 * 1000;
  // Anchor synthetic candles to "today 09:00 local" so the fallback never
  // appears days-stale in the TopBar. Previously hardcoded to 2026-04-29
  // which made the demo look outdated as soon as the date rolled over.
  const _now = new Date();
  const today = new Date(_now.getFullYear(), _now.getMonth(), _now.getDate(), 9, 0, 0, 0).getTime();

  const UNIVERSE = [
    {
      symbol: 'BTC/USDT',
      name: 'Bitcoin',
      exch: 'Binance',
      market: 'crypto',
      currency: 'USDT',
      gen: { seed: 7, n: N, start: 64200, vol: 0.028, drift: 0.0014, volBase: 38000, baseTime: today, intervalMs: day },
    },
    {
      symbol: '005930',
      name: '삼성전자',
      exch: 'KOSPI',
      market: 'kr',
      currency: 'KRW',
      gen: { seed: 31, n: N, start: 75800, vol: 0.018, drift: 0.0006, volBase: 12000000, baseTime: today, intervalMs: day },
    },
    {
      symbol: 'ETH/USDT',
      name: 'Ethereum',
      exch: 'Binance',
      market: 'crypto',
      currency: 'USDT',
      gen: { seed: 17, n: N, start: 3120, vol: 0.034, drift: 0.0011, volBase: 21000, baseTime: today, intervalMs: day },
    },
    {
      symbol: '000660',
      name: 'SK하이닉스',
      exch: 'KOSPI',
      market: 'kr',
      currency: 'KRW',
      gen: { seed: 53, n: N, start: 178000, vol: 0.024, drift: 0.0009, volBase: 4500000, baseTime: today, intervalMs: day },
    },
    {
      symbol: '035420',
      name: 'NAVER',
      exch: 'KOSPI',
      market: 'kr',
      currency: 'KRW',
      gen: { seed: 88, n: N, start: 192000, vol: 0.021, drift: -0.0003, volBase: 1900000, baseTime: today, intervalMs: day },
    },
    {
      symbol: 'SOL/USDT',
      name: 'Solana',
      exch: 'Binance',
      market: 'crypto',
      currency: 'USDT',
      gen: { seed: 121, n: N, start: 142, vol: 0.045, drift: 0.0018, volBase: 95000, baseTime: today, intervalMs: day },
    },
    {
      symbol: '373220',
      name: 'LG에너지솔루션',
      exch: 'KOSPI',
      market: 'kr',
      currency: 'KRW',
      gen: { seed: 64, n: N, start: 412000, vol: 0.022, drift: -0.0007, volBase: 380000, baseTime: today, intervalMs: day },
    },
    {
      symbol: '247540',
      name: '에코프로비엠',
      exch: 'KOSDAQ',
      market: 'kr',
      currency: 'KRW',
      gen: { seed: 99, n: N, start: 215000, vol: 0.034, drift: 0.0004, volBase: 720000, baseTime: today, intervalMs: day },
    },
  ];

  const DATA = {};
  UNIVERSE.forEach((u) => (DATA[u.symbol] = buildInstrument(u)));

  const BUY_KINDS = new Set(['golden_cross', 'rsi_oversold', 'macd_bull_cross', 'rsi_bull_div']);
  const SELL_KINDS = new Set(['death_cross', 'rsi_overbought', 'macd_bear_cross', 'rsi_bear_div']);
  function signalDirection(kind) {
    if (BUY_KINDS.has(kind)) return 'buy';
    if (SELL_KINDS.has(kind)) return 'sell';
    return 'neutral';
  }

  // Regime fit (ADX gate): trend-following signals (MA/MACD cross, divergence)
  // need a trend; RSI overbought/oversold works in chop. The per-bar `trend`
  // label already encodes the ADX regime (ADX<=25 -> 'side'). Returns
  // 'good' | 'weak' so the UI can de-emphasise regime-mismatched signals.
  function signalRegimeFit(kind, trend) {
    const trending = trend === 'up' || trend === 'down';
    // RSI overbought/oversold — a bounded oscillator: reliable in a sideways
    // market, unreliable in a trend (it stays pinned at the extreme).
    if (kind === 'rsi_overbought' || kind === 'rsi_oversold') {
      return trending ? 'weak' : 'good';
    }
    // Every other signal is directional (MA / MACD crosses, RSI divergence).
    // In a directionless market they whipsaw. In a trend they are trustworthy
    // only when the signal agrees with the trend direction — a counter-trend
    // signal (a sell inside a strong uptrend, including a bear divergence) is
    // usually a pullback or a premature top-call, not a reversal.
    if (!trending) return 'weak';
    const withTrend = (trend === 'up' && signalDirection(kind) === 'buy')
                   || (trend === 'down' && signalDirection(kind) === 'sell');
    return withTrend ? 'good' : 'weak';
  }

  // Build a synthetic instrument for an ad-hoc symbol added at runtime (demo
  // mode). Seed + starting price are derived deterministically from the symbol
  // string so the generated chart stays stable across reloads.
  function makeSyntheticInstrument(meta) {
    let h = 0;
    for (let i = 0; i < meta.symbol.length; i++) h = (h * 31 + meta.symbol.charCodeAt(i)) | 0;
    const abs = Math.abs(h);
    const isKr = meta.market === 'kr';
    const gen = {
      seed: (abs % 99999) + 1,
      n: N,
      start: isKr ? 10000 + (abs % 490000) : 1 + (Math.abs(h >> 3) % 60000),
      vol: isKr ? 0.020 : 0.035,
      drift: ((Math.abs(h >> 5) % 30) - 12) / 10000,
      volBase: isKr ? 2000000 : 50000,
      baseTime: today,
      intervalMs: day,
    };
    return buildInstrument(Object.assign({}, meta, { gen }));
  }

  window.MarketData = {
    UNIVERSE,
    DATA,
    makeSyntheticInstrument,
    helpers: { sma, ema, rsi, macd, bbands, rpb, wilderRma, classifyTrend, findCrosses, signalDirection, signalRegimeFit, BUY_KINDS, SELL_KINDS },
  };
})();
