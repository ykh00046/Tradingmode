"""Regression tests — bugs from the 2026-05-16 review session.

Each test pins a real-use path that previously passed unit tests while
failing in production. See `docs/02-design/features/improvement-plan.design.md`
§3 (P0-1). API-level cases (R-1/R-2/R-4/R-5) live here; the adapter-level
case (R-3, KR weekly/monthly tz) is in `tests/test_data_loader.py` because
`patch_fetch` would bypass `krx_adapter` entirely.
"""

from __future__ import annotations

import pytest


# Builtin strategy templates (Tradingmode/strategy-coach-page.jsx TEMPLATES).
# Every one uses `and` — the path that test_strategy.py's single-condition
# `_BASE_REQUEST` ("SMA_20 > SMA_60") never exercised. Plain `eval` resolves
# `and` via bool() short-circuit → "truth value of a Series is ambiguous", so
# all five builtin strategies were unrunnable while tests stayed green.
_BUILTIN_STRATEGIES = [
    pytest.param("Conservative RSI", "RSI_14 < 30 and ADX_14 > 20",
                 "RSI_14 > 70", id="Conservative RSI"),
    pytest.param("MA Crossover", "SMA_20 > SMA_60 and SMA_60 > SMA_120",
                 "SMA_20 < SMA_60", id="MA Crossover"),
    pytest.param("MACD Momentum", "MACDh_12_26_9 > 0 and MACD_12_26_9 > MACDs_12_26_9",
                 "MACDh_12_26_9 < 0", id="MACD Momentum"),
    # BB columns renamed dot-free (BBL_20 etc.) so the DSL can parse them —
    # the dotted `BBL_20_2.0_2.0` previously broke ast.parse.
    pytest.param("BB Squeeze", "close < BBL_20 and RSI_14 < 40",
                 "close > BBM_20", id="BB Squeeze"),
    pytest.param("RSI Imminent", "close < RPB_DN_30 and RPB_DN_30_BARS > -1.5",
                 "close > RPB_UP_70", id="RSI Imminent"),
]

_BASE = {
    "market": "crypto",
    "symbol": "BTCUSDT",
    "interval": "1d",
    "start": 1704067200000,
    "end": 1721347200000,
    "split_ratio": 0.7,
    "cash": 1_000_000,
    "persist": False,
}
_QUERY = {
    "market": "crypto", "symbol": "BTCUSDT", "interval": "1d",
    "start": 1704067200000, "end": 1721347200000,
}


# --- R-1 — every builtin strategy backtests without the and/or eval crash ---
@pytest.mark.parametrize("name,buy_when,sell_when", _BUILTIN_STRATEGIES)
def test_R1_builtin_strategies_backtest(client, patch_fetch, name, buy_when, sell_when) -> None:
    body = {**_BASE, "strategy": {
        "name": name, "buy_when": buy_when, "sell_when": sell_when,
        "optimization_goal": "sharpe",
    }}
    res = client.post("/api/strategy/backtest", json=body)
    assert res.status_code == 200, f"{name}: {res.text}"
    is_result = res.json()["is_result"]
    assert isinstance(is_result["total_return"], (int, float))


# --- R-2 — `or` and `not` evaluate element-wise too (builtins only use `and`) ---
def test_R2_or_and_not_expressions(client, patch_fetch) -> None:
    body = {**_BASE, "strategy": {
        "name": "or/not probe",
        "buy_when": "RSI_14 < 30 or (not (SMA_20 < SMA_60))",
        "sell_when": "RSI_14 > 70 or RSI_14 < 25",
        "optimization_goal": "sharpe",
    }}
    res = client.post("/api/strategy/backtest", json=body)
    assert res.status_code == 200, res.text


def _first_non_null(seq: list) -> int | None:
    return next((i for i, v in enumerate(seq) if v is not None), None)


# --- R-4 — MACD signal line warms up *after* the MACD line (not zero-seeded) ---
def test_R4_macd_signal_warmup(client, patch_fetch) -> None:
    res = client.get("/api/indicators", params=_QUERY)
    assert res.status_code == 200, res.text
    ind = res.json()["indicators"]
    line_first = _first_non_null(ind["MACD_12_26_9"])
    sig_first = _first_non_null(ind["MACDs_12_26_9"])
    assert line_first is not None and sig_first is not None
    # The signal is an EMA *of* the MACD line — it must warm up strictly later
    # than the line. A zero-seeded signal would start at the line's first bar.
    assert sig_first > line_first, f"signal {sig_first} not warmed past line {line_first}"
    assert sig_first - line_first >= 5
    assert all(v is not None for v in ind["MACDs_12_26_9"][sig_first:]), "contiguous after warmup"


# --- R-5 — signals carry a non-empty kind and an int ms timestamp ---
def test_R5_signals_shape(client, patch_fetch) -> None:
    res = client.get("/api/signals", params=_QUERY)
    assert res.status_code == 200, res.text
    for s in res.json()["signals"]:
        assert isinstance(s["kind"], str) and s["kind"]
        assert isinstance(s["timestamp"], int)
