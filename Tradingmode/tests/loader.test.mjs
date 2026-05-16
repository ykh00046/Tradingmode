import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const loaderPath = path.join(__dirname, '..', 'loader.js');

function buildIndicatorPayload(candles, opts = {}) {
  const n = candles.length;
  // RPB columns expected by buildInd — 12 keys (UP/DN × thresholds × value/bars).
  const rpb = {
    RPB_UP_70: Array(n).fill(108), RPB_UP_75: Array(n).fill(109), RPB_UP_80: Array(n).fill(110),
    RPB_DN_30: Array(n).fill(92),  RPB_DN_25: Array(n).fill(91),  RPB_DN_20: Array(n).fill(90),
    RPB_UP_70_BARS: Array(n).fill(0), RPB_UP_75_BARS: Array(n).fill(0), RPB_UP_80_BARS: Array(n).fill(0),
    RPB_DN_30_BARS: Array(n).fill(0), RPB_DN_25_BARS: Array(n).fill(0), RPB_DN_20_BARS: Array(n).fill(0),
  };
  return {
    SMA_20: Array(n).fill(100),
    SMA_60: Array(n).fill(99),
    SMA_120: Array(n).fill(98),
    RSI_14: Array(n).fill(55),
    MACD_12_26_9: Array(n).fill(0.4),
    MACDs_12_26_9: Array(n).fill(0.2),
    MACDh_12_26_9: Array(n).fill(0.2),
    BBM_20: Array(n).fill(100),
    BBU_20: Array(n).fill(110),
    BBL_20: Array(n).fill(90),
    ...(opts.includeRpb !== false ? rpb : {}),
    // For padding test: provide a deliberately-short SMA_20 series (length 2)
    // so getColumn must front-pad with nulls to reach candle length.
    ...(opts.short ? { SMA_20: [100, 100] } : {}),
  };
}

function createLoaderContext(overrides = {}) {
  const code = readFileSync(loaderPath, 'utf8');
  const candles = overrides.candles || [
    { t: 1714521600000, o: 100, h: 110, l: 95, c: 105, v: 1000 },
    { t: 1714608000000, o: 105, h: 115, l: 100, c: 112, v: 1200 },
    { t: 1714694400000, o: 112, h: 120, l: 108, c: 118, v: 1500 },
  ];
  let indicatorCalls = 0;
  const context = {
    console,
    URL,
    setTimeout,
    clearTimeout,
    window: {
      api: {
        dateRange: () => ({ start: 1, end: 2 }),
        indicators: overrides.indicators || (async () => {
          indicatorCalls += 1;
          return { candles, indicators: buildIndicatorPayload(candles, overrides) };
        }),
        signals: overrides.signals || (async () => ({
          signals: [
            { timestamp: candles[1].t, kind: 'golden_cross', strength: 1.0 },
            { timestamp: 1, kind: 'rsi_overbought', strength: 0.8 }, // stale, out of range
          ],
        })),
        backtest: overrides.backtest || (async () => {
          throw new Error('backtest unavailable');
        }),
      },
      MarketData: {
        DATA: {},
        helpers: {
          ema: (values) => values.map(() => null),
          classifyTrend: (values) => values.map(() => 'side'),
          findCrosses: () => [],
        },
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  return { context, candles, getIndicatorCalls: () => indicatorCalls };
}

async function testHappyPath() {
  const { context, candles } = createLoaderContext();
  const instrument = await context.window.loader.loadInstrument({
    symbol: 'BTC/USDT', market: 'crypto', name: 'Bitcoin', currency: 'USDT', exch: 'BINANCE',
  });
  assert.equal(instrument.candles.length, candles.length);
  assert.equal(instrument.candles[1].c, 112);
  // Stale out-of-range signal filtered, only in-range one survives.
  assert.equal(instrument.signals.length, 1);
  assert.equal(instrument.signals[0].kind, 'golden_cross');
  assert.equal(Array.isArray(instrument.trades), true);
  assert.equal(instrument.trades.length, 0);
  assert.equal(instrument.stats.totalReturn, 0);
  assert.equal(instrument.equity.length, candles.length);
  assert.equal(instrument.equity[0].eq, 1);
}

async function testRpbNestedShape() {
  const { context } = createLoaderContext();
  const instrument = await context.window.loader.loadInstrument({
    symbol: 'BTC/USDT', market: 'crypto', name: 'Bitcoin', currency: 'USDT', exch: 'BINANCE',
  });
  // RPB must be wired into the nested {up:{70/75/80}, dn:{30/25/20}, bars:{...}} shape.
  assert.ok(instrument.ind.rpb, 'rpb should exist');
  assert.equal(instrument.ind.rpb.up[70][0], 108);
  assert.equal(instrument.ind.rpb.up[75][0], 109);
  assert.equal(instrument.ind.rpb.up[80][0], 110);
  assert.equal(instrument.ind.rpb.dn[30][0], 92);
  assert.equal(instrument.ind.rpb.dn[25][0], 91);
  assert.equal(instrument.ind.rpb.dn[20][0], 90);
  assert.equal(instrument.ind.rpb.bars.up[70][0], 0);
  assert.equal(instrument.ind.rpb.bars.dn[20][0], 0);
}

async function testGetColumnLengthMismatchPadding() {
  // SMA_20 has only 2 entries against 3 candles — getColumn must front-pad
  // with nulls so indices stay aligned with candles.
  const { context, candles } = createLoaderContext({ short: true });
  const instrument = await context.window.loader.loadInstrument({
    symbol: 'BTC/USDT', market: 'crypto', name: 'Bitcoin', currency: 'USDT', exch: 'BINANCE',
  });
  assert.equal(instrument.ind.ma20.length, candles.length, 'ma20 must be padded to candle length');
  // Front-pad: with 3 candles + 2-entry series, position 0 should be null,
  // positions 1 and 2 should carry the tail values.
  assert.equal(instrument.ind.ma20[0], null, 'short series should be front-padded with nulls');
  assert.equal(instrument.ind.ma20[candles.length - 1], 100, 'tail values preserved');
}

async function testBacktestMapperEnrichesFields() {
  // Backend emits CamelCase trade rows with EntryBar/ExitBar — the mapper
  // must populate entryI/exitI/hold/open so BacktestPage never sees undefined.
  const candles = [
    { t: 1714521600000, o: 100, h: 110, l: 95, c: 105, v: 1000 },
    { t: 1714608000000, o: 105, h: 115, l: 100, c: 112, v: 1200 },
    { t: 1714694400000, o: 112, h: 120, l: 108, c: 118, v: 1500 },
    { t: 1714780800000, o: 118, h: 125, l: 115, c: 122, v: 1700 },
  ];
  const { context } = createLoaderContext({
    candles,
    backtest: async () => ({
      total_return: 5.0,
      win_rate: 100,
      max_drawdown: -2.0,
      num_trades: 1,
      sharpe_ratio: 1.2,
      equity_curve: candles.map((c, i) => ({ t: c.t, equity: 1 + i * 0.01 })),
      trades: [
        { EntryTime: candles[0].t, ExitTime: candles[2].t, EntryPrice: 105, ExitPrice: 118, ReturnPct: 12.4, EntryBar: 0, ExitBar: 2 },
      ],
    }),
  });
  const instrument = await context.window.loader.loadInstrument({
    symbol: 'BTC/USDT', market: 'crypto', name: 'Bitcoin', currency: 'USDT', exch: 'BINANCE',
  });
  assert.equal(instrument.trades.length, 1);
  const t = instrument.trades[0];
  assert.equal(t.entryI, 0, 'entryI must come from EntryBar');
  assert.equal(t.exitI, 2, 'exitI must come from ExitBar');
  assert.equal(t.hold, 2, 'hold = exitI - entryI');
  assert.equal(t.open, false, 'backtesting.py synthetically closes — open is always false');
  assert.equal(Math.round(t.ret * 10000) / 10000, 0.124, 'ReturnPct converted to fraction');
}

async function testAbortDoesNotRetry() {
  // loadInstrumentWithRetry must NOT retry when the user-issued AbortController
  // fires (e.g. symbol changed mid-flight).
  let calls = 0;
  const { context } = createLoaderContext({
    indicators: async () => {
      calls += 1;
      const err = new Error('aborted'); err.name = 'AbortError';
      throw err;
    },
  });
  // loadAllInstruments wraps with retry; loadInstrument itself doesn't.
  const universe = [{ symbol: 'BTC/USDT', market: 'crypto', name: 'Bitcoin', currency: 'USDT', exch: 'BINANCE' }];
  await context.window.loader.loadAllInstruments(universe, {});
  // AbortError should be caught and NOT retried — exactly one call.
  assert.equal(calls, 1, `AbortError should not trigger retry, got ${calls} calls`);
}

async function main() {
  await testHappyPath();
  await testRpbNestedShape();
  await testGetColumnLengthMismatchPadding();
  await testBacktestMapperEnrichesFields();
  await testAbortDoesNotRetry();
  console.log('all loader tests passed');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
