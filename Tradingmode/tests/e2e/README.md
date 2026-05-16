# Frontend E2E smoke test

`smoke.py` — P0-2 of the improvement plan. Loads the app in **demo mode**
and verifies every tab renders with zero uncaught JS errors, plus four core
interactions (watchlist symbol switch, indicator toggle, interval switch,
signal feed expand).

It is **self-contained**: it spawns its own static server on port `5599`
(so it never collides with a dev server on `:5500`), runs headless
Chromium, and tears the server down on exit.

## Prerequisites

```bash
pip install -r backend/requirements-dev.txt
playwright install chromium          # one-time browser download
```

## Run

```bash
cd Tradingmode
python tests/e2e/smoke.py
```

Exit code `0` = all checks passed, `1` = any failure. Each check prints
`PASS` / `FAIL` so the failing tab/interaction is obvious.

## What it covers (and what it does not)

- ✅ All 5 tabs render without JS errors (`.chart-page`, `.signals-page`,
  `.backtest-page`, `.portfolio-page`, `.strategy-coach-page`).
- ✅ Core interactions don't throw.
- ❌ Backend-dependent flows (live data, strategy backtest values) — those
  are covered by the backend regression suite (`backend/tests/test_api/
  test_regression.py`, P0-1). Demo mode keeps this test offline and fast.
