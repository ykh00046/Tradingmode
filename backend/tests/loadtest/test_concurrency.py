"""Load / concurrency tests for the P6 (parallel fan-out) refactor.

Each test injects a deterministic sleep into the per-unit blocking call and
verifies that the parallelisation actually parallelises — i.e. wall-clock
elapsed time is closer to ``sleep`` than to ``N * sleep``.

Tests are wall-clock sensitive but use generous tolerances; they should pass
on slow CI hosts. If a test starts flaking, raise the tolerance rather than
removing it — the *shape* of the timing assertion is what matters.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pandas as pd
import pytest

from core import market_snapshot, portfolio
from core.types.schemas import (
    FxQuote,
    Holding,
    HoldingAnalysis,
    IndexQuote,
    Market,
    Portfolio,
    TrendState,
)


# =============================================================================
# Portfolio — per-holding analysis must run in parallel (max_workers=4)
# =============================================================================


def _make_portfolio(n: int) -> Portfolio:
    return Portfolio(
        holdings=[
            Holding(
                market=Market.CRYPTO,
                symbol=f"S{i}",
                quantity=1.0,
                avg_price=100.0,
                currency="USDT",
            )
            for i in range(n)
        ],
        base_currency="USD",
    )


def _fake_analysis(holding: Holding, *_args, **_kwargs) -> HoldingAnalysis:
    return HoldingAnalysis(
        holding=holding,
        current_price_local=100.0,
        current_price=100.0,
        market_value=100.0,
        cost_basis=100.0,
        pnl=0.0,
        pnl_pct=0.0,
        weight=0.0,
        fx_rate=1.0,
        trend=TrendState.SIDEWAYS,
        latest_signals=[],
    )


def test_portfolio_analyze_parallel_speedup() -> None:
    """10 holdings × 0.4s sleep should finish well under serial 4.0s.

    With max_workers=4 the expected wall-clock is ~1.2s (10 holdings / 4 lanes
    × 0.4s + scheduling overhead). Assert <2.0s to leave plenty of slack on
    slow CI.
    """
    SLEEP_S = 0.4
    N_HOLDINGS = 10
    SERIAL_BUDGET = N_HOLDINGS * SLEEP_S  # 4.0s
    PARALLEL_BUDGET = 2.0                  # ~ half of serial — clear evidence of parallelism

    def slow_analysis(holding: Holding, *args, **kwargs) -> HoldingAnalysis:
        time.sleep(SLEEP_S)
        return _fake_analysis(holding, *args, **kwargs)

    with patch("core.portfolio._analyze_holding", slow_analysis), \
         patch("core.portfolio._resolve_fx_rates", return_value={}):
        t0 = time.monotonic()
        result = portfolio.analyze(_make_portfolio(N_HOLDINGS))
        elapsed = time.monotonic() - t0

    assert len(result.holdings_analysis) == N_HOLDINGS
    assert elapsed < PARALLEL_BUDGET, (
        f"portfolio.analyze took {elapsed:.2f}s for {N_HOLDINGS} holdings × "
        f"{SLEEP_S}s sleep — expected <{PARALLEL_BUDGET}s (serial would be "
        f"{SERIAL_BUDGET}s). Possibly running serially."
    )
    # Sanity: must take at least 2 batches of sleep (cap at 4 workers)
    min_expected = SLEEP_S * (N_HOLDINGS / 4) * 0.8
    assert elapsed >= min_expected, (
        f"portfolio.analyze took {elapsed:.2f}s — suspiciously fast, sleeps "
        f"may not be running. min expected {min_expected:.2f}s"
    )


def test_portfolio_analyze_results_stable_under_concurrency() -> None:
    """Out-of-order ThreadPoolExecutor completion must not affect output order."""

    def slow_analysis(holding: Holding, *args, **kwargs) -> HoldingAnalysis:
        # Reverse-correlated sleep — later symbols finish first.
        idx = int(holding.symbol[1:])
        time.sleep(0.05 + (5 - idx) * 0.02)
        return _fake_analysis(holding, *args, **kwargs)

    with patch("core.portfolio._analyze_holding", slow_analysis), \
         patch("core.portfolio._resolve_fx_rates", return_value={}):
        result = portfolio.analyze(_make_portfolio(5))

    symbols = [a.holding.symbol for a in result.holdings_analysis]
    assert symbols == sorted(symbols), (
        f"holdings_analysis order is unstable: {symbols}. Should be sorted "
        f"by (market, symbol) regardless of completion order."
    )


# =============================================================================
# Market snapshot — 6 fetchers must run in parallel
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_snapshot_cache():
    """Each test starts with a cold cache so we measure the cold-path latency."""
    market_snapshot._cache.clear()
    yield
    market_snapshot._cache.clear()


def test_market_snapshot_fans_out_six_calls() -> None:
    """6 fetchers × 0.3s sleep should finish in ~0.3-0.5s, not 1.8s."""
    SLEEP_S = 0.3
    SERIAL_BUDGET = 6 * SLEEP_S            # 1.8s
    PARALLEL_BUDGET = 1.2                   # generous for windows scheduling

    def slow_fdr(ticker, *, fallback):
        time.sleep(SLEEP_S)
        return IndexQuote(value=100.0, change_pct=0.5)

    def slow_btc():
        time.sleep(SLEEP_S)
        return IndexQuote(value=50000.0, change_pct=1.0)

    with patch("core.market_snapshot._fdr_index_quote", side_effect=slow_fdr), \
         patch("core.market_snapshot._btc_quote", side_effect=slow_btc):
        t0 = time.monotonic()
        snap = market_snapshot.fetch_snapshot(force_refresh=True)
        elapsed = time.monotonic() - t0

    assert snap.kospi.value == 100.0
    assert snap.btc.value == 50000.0
    assert elapsed < PARALLEL_BUDGET, (
        f"fetch_snapshot took {elapsed:.2f}s — expected <{PARALLEL_BUDGET}s "
        f"(serial would be {SERIAL_BUDGET}s). The 6 fetchers are not running "
        f"in parallel."
    )


def test_market_snapshot_single_flight_on_cold_cache() -> None:
    """Two concurrent first-hits must collapse to ONE upstream fan-out.

    Regression test for the threading.Lock added in P4 — without it, two
    threads racing into a cold cache would both fan out 6 fetches each.
    """
    call_count = {"n": 0}

    def slow_fdr(ticker, *, fallback):
        time.sleep(0.2)  # long enough that both threads arrive before the first finishes
        call_count["n"] += 1
        return IndexQuote(value=100.0, change_pct=0.5)

    def slow_btc():
        time.sleep(0.2)
        call_count["n"] += 1
        return IndexQuote(value=50000.0, change_pct=1.0)

    with patch("core.market_snapshot._fdr_index_quote", side_effect=slow_fdr), \
         patch("core.market_snapshot._btc_quote", side_effect=slow_btc):
        # Fire 2 cold-cache requests concurrently.
        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(market_snapshot.fetch_snapshot)
            f2 = ex.submit(market_snapshot.fetch_snapshot)
            s1 = f1.result()
            s2 = f2.result()

    # Both responses must be served. Single-flight means upstream called exactly once
    # — 6 fetcher calls total (5 fdr + 1 btc), not 12.
    assert s1.timestamp == s2.timestamp, "both requests should see the same snapshot"
    assert call_count["n"] == 6, (
        f"single-flight broken: expected 6 upstream calls (5 fdr + 1 btc), "
        f"got {call_count['n']}. Concurrent cold-cache requests are duplicating fan-out."
    )


def test_market_snapshot_cache_hit_is_fast() -> None:
    """Warm-cache lookups must be sub-millisecond — no lock acquisition needed."""

    with patch("core.market_snapshot._fdr_index_quote", return_value=IndexQuote(100.0, 0.5)), \
         patch("core.market_snapshot._btc_quote", return_value=IndexQuote(50000.0, 1.0)):
        market_snapshot.fetch_snapshot(force_refresh=True)  # warm the cache

        t0 = time.monotonic()
        for _ in range(1000):
            market_snapshot.fetch_snapshot()
        elapsed = time.monotonic() - t0

    avg_us = (elapsed / 1000) * 1_000_000
    assert avg_us < 200, (
        f"warm-cache fetch_snapshot avg {avg_us:.0f}µs over 1000 calls — "
        f"expected <200µs. Lock contention or extra work on the hot path?"
    )
