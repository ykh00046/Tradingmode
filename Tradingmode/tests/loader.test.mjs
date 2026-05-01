import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const loaderPath = path.join(__dirname, '..', 'loader.js');

function createLoaderContext() {
  const code = readFileSync(loaderPath, 'utf8');
  const candles = [
    { t: 1714521600000, o: 100, h: 110, l: 95, c: 105, v: 1000 },
    { t: 1714608000000, o: 105, h: 115, l: 100, c: 112, v: 1200 },
  ];
  const context = {
    console,
    URL,
    setTimeout,
    clearTimeout,
    window: {
      api: {
        dateRange: () => ({ start: 1, end: 2 }),
        indicators: async () => ({
          candles,
          indicators: {
            SMA_20: [100, 101],
            SMA_60: [99, 100],
            SMA_120: [98, 99],
            RSI_14: [55, 58],
            MACD_12_26_9: [0.4, 0.6],
            MACDs_12_26_9: [0.2, 0.3],
            MACDh_12_26_9: [0.2, 0.3],
            "BBM_20_2.0_2.0": [100, 101],
            "BBU_20_2.0_2.0": [110, 112],
            "BBL_20_2.0_2.0": [90, 92],
          },
        }),
        signals: async () => ({
          signals: [
            { timestamp: candles[1].t, kind: 'golden_cross', strength: 1.0 },
          ],
        }),
        backtest: async () => {
          throw new Error('backtest unavailable');
        },
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
  return { context, candles };
}

async function main() {
  const { context, candles } = createLoaderContext();
  const instrument = await context.window.loader.loadInstrument({
    symbol: 'BTC/USDT',
    market: 'crypto',
    name: 'Bitcoin',
    currency: 'USDT',
    exch: 'BINANCE',
  });

  assert.equal(instrument.candles.length, candles.length);
  assert.equal(instrument.candles[1].c, 112);
  assert.equal(instrument.signals.length, 1);
  assert.equal(Array.isArray(instrument.trades), true);
  assert.equal(instrument.trades.length, 0);
  assert.equal(instrument.stats.totalReturn, 0);
  assert.equal(instrument.stats.trades, 0);
  assert.equal(instrument.equity.length, candles.length);
  assert.equal(instrument.equity[0].eq, 1);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
