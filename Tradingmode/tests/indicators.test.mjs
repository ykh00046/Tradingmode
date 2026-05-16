// P1-1 — indicator golden snapshot test.
//
// data.js (demo mode) and the backend (live mode) are two separate indicator
// implementations. They cannot be byte-identical (different EMA/Wilder seeding
// conventions), so this is NOT a data.js-vs-backend parity test. Instead it
// pins data.js's *own* output for a fixed input as a golden snapshot: any
// accidental change to a data.js indicator (drift) fails the test.
//
// The fixture is RNG- and transcendental-free, so the snapshot is byte-stable
// across machines. First run bootstraps the golden file; rerun to verify.
//
// Run:  node --test tests/indicators.test.mjs

import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dataPath = path.join(__dirname, '..', 'data.js');
const fixturesDir = path.join(__dirname, 'fixtures');
const goldenPath = path.join(fixturesDir, 'indicator-golden.json');

// data.js is a browser IIFE — load it in a vm with a `window` global and read
// window.MarketData.helpers (same approach as loader.test.mjs).
function loadHelpers() {
  const code = readFileSync(dataPath, 'utf8');
  const ctx = { window: {}, console };
  vm.createContext(ctx);
  vm.runInContext(code, ctx);
  return ctx.window.MarketData.helpers;
}

// Deterministic OHLCV fixture — pure integer/float arithmetic only (no RNG,
// no Math.sin/cos/pow), so golden generation and verification are byte-stable.
function fixtureCandles(n = 250) {
  const cs = [];
  let c = 100;
  for (let i = 0; i < n; i++) {
    const step = ((i * 7 + 13) % 23) - 11;          // integer in [-11, 11]
    c = c + step * 0.25 + 0.15;                      // oscillation + slight drift
    const o = i === 0 ? 100 : cs[i - 1].c;
    cs.push({ t: i, o, h: Math.max(o, c) + 1, l: Math.min(o, c) - 1, c, v: 1000 + i });
  }
  return cs;
}

function computeAll(h) {
  const candles = fixtureCandles();
  const closes = candles.map((c) => c.c);
  return {
    sma20:  h.sma(closes, 20),
    ema12:  h.ema(closes, 12),
    rsi14:  h.rsi(closes, 14),
    macd:   h.macd(closes),
    bbands: h.bbands(closes, 20, 2),
    rpb:    h.rpb(candles),
  };
}

function main() {
  const helpers = loadHelpers();
  // §5.2 step 0 — rpb / wilderRma must be exported on helpers.
  for (const fn of ['sma', 'ema', 'rsi', 'macd', 'bbands', 'rpb', 'wilderRma']) {
    assert.equal(typeof helpers[fn], 'function', `helpers.${fn} must be exported`);
  }

  const fresh = computeAll(helpers);

  if (!existsSync(goldenPath)) {
    mkdirSync(fixturesDir, { recursive: true });
    writeFileSync(goldenPath, JSON.stringify(fresh));
    console.log('golden snapshot created — rerun to verify:', goldenPath);
    return;
  }

  // data.js indicators are pure and the fixture is RNG-free → exact match.
  const golden = JSON.parse(readFileSync(goldenPath, 'utf8'));
  for (const key of Object.keys(fresh)) {
    assert.equal(
      JSON.stringify(fresh[key]),
      JSON.stringify(golden[key]),
      `indicator '${key}' drifted from the golden snapshot — if intentional, ` +
      `delete tests/fixtures/${path.basename(goldenPath)} and rerun to regenerate`,
    );
  }
  console.log('all 6 indicators match the golden snapshot');
}

try {
  main();
} catch (error) {
  console.error(error);
  process.exitCode = 1;
}
