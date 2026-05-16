"""Unit tests for ``core.data_loader``.

Adapters and the cache layer are mocked so these run without network access
or pandas-ta.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core import data_loader
from core.types.schemas import FetchRequest, Interval, Market


def _fake_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [95.0] * 10,
            "close": [102.0] * 10,
            "volume": [1000.0] * 10,
        },
        index=idx,
    )


def _make_request(market: Market = Market.CRYPTO) -> FetchRequest:
    return FetchRequest(
        market=market,
        symbol="BTCUSDT",
        interval=Interval.D1,
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-10"),
    )


def test_cache_miss_calls_adapter_and_saves(mocker, writable_tmp_dir) -> None:
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download", return_value=fake)
    krx_dl = mocker.patch("core.data_loader.krx_adapter.download")

    result, cache_hit = data_loader.fetch(_make_request(Market.CRYPTO))

    assert bin_dl.call_count == 1
    assert krx_dl.call_count == 0
    assert cache_hit is False
    pd.testing.assert_frame_equal(result, fake)


def test_cache_hit_skips_adapter(mocker, writable_tmp_dir) -> None:
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download", return_value=fake)

    # First call populates cache, second call should hit it.
    data_loader.fetch(_make_request(Market.CRYPTO))
    bin_dl.reset_mock()

    _, cache_hit = data_loader.fetch(_make_request(Market.CRYPTO))
    assert bin_dl.call_count == 0
    assert cache_hit is True


def test_routes_kr_market_to_krx_adapter(mocker, writable_tmp_dir) -> None:
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download")
    krx_dl = mocker.patch("core.data_loader.krx_adapter.download", return_value=fake)

    req = FetchRequest(
        market=Market.KR_STOCK,
        symbol="005930",
        interval=Interval.D1,
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-10"),
    )
    data_loader.fetch(req)

    assert krx_dl.call_count == 1
    assert bin_dl.call_count == 0


def test_invalid_symbol_does_not_create_cache_entry(mocker, writable_tmp_dir) -> None:
    from core.types.errors import InvalidSymbolError

    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    mocker.patch(
        "core.data_loader.binance_adapter.download",
        side_effect=InvalidSymbolError("nope"),
    )

    with pytest.raises(InvalidSymbolError):
        data_loader.fetch(_make_request(Market.CRYPTO))

    # No parquet files should have been written.
    assert not list(writable_tmp_dir.rglob("*.parquet"))


# =============================================================================
# v0.8 longer-intervals — KR weekly/monthly resample (T-B1 ~ T-B4)
# =============================================================================


def _kr_daily_df(num_days: int, start_date: str = "2024-01-01") -> pd.DataFrame:
    """Generate a deterministic daily OHLCV DataFrame for resample testing."""
    idx = pd.date_range(start_date, periods=num_days, freq="D")
    return pd.DataFrame(
        {
            "open":   [100.0 + i for i in range(num_days)],
            "high":   [105.0 + i for i in range(num_days)],
            "low":    [95.0 + i for i in range(num_days)],
            "close":  [102.0 + i for i in range(num_days)],
            "volume": [1000.0 + i * 10 for i in range(num_days)],
        },
        index=idx,
    )


def _kr_request(interval: Interval, days: int = 60) -> "FetchRequest":
    return FetchRequest(
        market=Market.KR_STOCK,
        symbol="005930",
        interval=interval,
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-01") + pd.Timedelta(days=days),
    )


def test_kr_resample_weekly_ohlcv_correct(mocker, writable_tmp_dir) -> None:
    """T-B1: 10 daily rows resampled to weekly produces exactly 2 buckets.

    pandas W-FRI groups by week-ending-Friday. With 10 calendar days starting
    Mon 2024-01-01, weekend dates fall into the *following* week-end bucket:
      - 2024-01-05 (Fri): 1/1 (Mon) .. 1/5 (Fri)  → 5 rows
      - 2024-01-12 (Fri): 1/6 (Sat) .. 1/10 (Wed) → 5 rows (incl. weekends)
    Final count = exactly 2 buckets. (14-day fixture would create a partial
    third bucket because 1/13–1/14 weekend rolls into bucket ending 1/19.)
    """
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    daily = _kr_daily_df(num_days=10, start_date="2024-01-01")
    mocker.patch("core.adapters.krx_adapter._try_pykrx", return_value=daily)

    result, _ = data_loader.fetch(_kr_request(Interval.W1, days=10))

    assert len(result) == 2, f"expected exactly 2 weekly bars, got {len(result)}"
    # First weekly bar = indices 0..4 (1/1 Mon .. 1/5 Fri):
    first = result.iloc[0]
    assert first["open"] == 100.0,  "weekly open = first daily open (Mon)"
    assert first["high"] == 109.0,  "weekly high = max of 5 daily highs (105..109)"
    assert first["low"] == 95.0,    "weekly low = min of 5 daily lows"
    assert first["close"] == 106.0, "weekly close = last daily close (Fri)"
    assert first["volume"] == sum(1000.0 + i * 10 for i in range(5)), "weekly volume = sum"
    # Second weekly bar = indices 5..9 (1/6 Sat .. 1/10 Wed, weekends included):
    second = result.iloc[1]
    assert second["open"] == 105.0,  "weekly open = open of index 5"
    assert second["close"] == 111.0, "weekly close = close of index 9"


def test_kr_resample_monthly_ohlcv_correct(mocker, writable_tmp_dir) -> None:
    """T-B2: 60 daily rows resampled to monthly produces correct OHLCV.

    2024-01-01 (Mon) start, 60 days → covers Jan 1 .. Feb 29 (60 calendar days).
    ME buckets: Jan 31 (31 daily rows: indices 0..30) + Feb 29 (29 daily rows: 31..59).
    Final count = exactly 2 buckets.
    """
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    daily = _kr_daily_df(num_days=60, start_date="2024-01-01")
    mocker.patch("core.adapters.krx_adapter._try_pykrx", return_value=daily)

    result, _ = data_loader.fetch(_kr_request(Interval.MN1, days=60))

    assert len(result) == 2, f"expected exactly 2 monthly bars, got {len(result)}"
    # First monthly bar = January 2024 (indices 0..30, 31 rows):
    first = result.iloc[0]
    assert first["open"] == 100.0,           "monthly open = first daily open"
    assert first["high"] == 100.0 + 30 + 5,  "monthly high = max over Jan (i=30 → 135)"
    assert first["low"] == 95.0,             "monthly low = min over Jan"
    assert first["close"] == 102.0 + 30,     "monthly close = last close in Jan (132)"
    # Second monthly bar = February 2024 (indices 31..59, 29 rows):
    second = result.iloc[1]
    assert second["open"] == 100.0 + 31,     "monthly open = open of index 31"
    assert second["close"] == 102.0 + 59,    "monthly close = close of index 59"


def test_kr_insufficient_data_raises_data_source_error(mocker, writable_tmp_dir) -> None:
    """T-B3: 3 daily rows < min 5 for weekly → minimum-bars guard fires.

    This is the real production scenario (newly-listed symbol). The guard
    short-circuits BEFORE resample, so partial buckets never leak.
    """
    from core.types.errors import DataSourceError

    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    daily = _kr_daily_df(num_days=3)  # real data, NOT NaN-injected
    mocker.patch("core.adapters.krx_adapter._try_pykrx", return_value=daily)

    with pytest.raises(DataSourceError, match="need at least 5") as exc_info:
        data_loader.fetch(_kr_request(Interval.W1, days=3))

    err = exc_info.value
    assert err.details["daily_rows"] == 3
    assert err.details["min_required"] == 5
    assert err.details["interval"] == "1w"


def test_kr_all_nan_closes_raises_data_source_error(mocker, writable_tmp_dir) -> None:
    """T-B3b: enough daily rows but all-NaN closes → empty resample → error.

    Defensive check for the path where minimum-bars guard passes but the
    upstream returned a malformed DataFrame.
    """
    from core.types.errors import DataSourceError

    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    daily = _kr_daily_df(num_days=10)  # > min 5 for weekly
    daily["close"] = float("nan")
    mocker.patch("core.adapters.krx_adapter._try_pykrx", return_value=daily)

    with pytest.raises(DataSourceError, match="all-NaN closes"):
        data_loader.fetch(_kr_request(Interval.W1, days=10))


def test_binance_weekly_monthly_routed_natively(mocker, writable_tmp_dir) -> None:
    """T-B4: 1w / 1M crypto requests go to binance adapter, not krx."""
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download", return_value=fake)
    krx_dl = mocker.patch("core.data_loader.krx_adapter.download")

    for iv in (Interval.W1, Interval.MN1):
        req = FetchRequest(
            market=Market.CRYPTO,
            symbol="BTCUSDT",
            interval=iv,
            start=pd.Timestamp("2024-01-01"),
            end=pd.Timestamp("2024-12-01"),
        )
        data_loader.fetch(req)

    assert bin_dl.call_count == 2, "binance.download should be called for both 1w and 1M"
    assert krx_dl.call_count == 0, "krx.download must not be invoked for crypto"
    # Verify the interval string was passed through unchanged
    called_intervals = [c.args[1] for c in bin_dl.call_args_list]
    assert "1w" in called_intervals
    assert "1M" in called_intervals


def test_kr_resample_accepts_tz_aware_start(mocker, writable_tmp_dir) -> None:
    """R-3 (regression, 2026-05-16) — KR weekly/monthly resample with a
    *tz-aware* ``start``.

    The real API path builds ``start`` via ``converters.ms_to_ts``, which
    returns a tz-aware (UTC) Timestamp. ``krx_adapter`` trims the resampled
    frame with ``resampled.index >= start``; the resampled index is tz-naive,
    so a tz-aware ``start`` raised ``TypeError: Invalid comparison``. The T-B
    tests above use a naive ``start`` and never exercised this path.
    """
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    daily = _kr_daily_df(num_days=60, start_date="2024-01-01")
    mocker.patch("core.adapters.krx_adapter._try_pykrx", return_value=daily)

    for interval in (Interval.W1, Interval.MN1):
        req = FetchRequest(
            market=Market.KR_STOCK,
            symbol="005930",
            interval=interval,
            start=pd.Timestamp("2024-01-01", tz="UTC"),   # tz-aware — real API path
            end=pd.Timestamp("2024-04-01", tz="UTC"),
        )
        result, _ = data_loader.fetch(req)
        assert len(result) > 0, f"{interval.value}: expected resampled candles"


# =============================================================================
# Schema sync — Interval enum (core) vs IntervalLiteral (api)
# =============================================================================


def test_interval_enum_matches_api_literal() -> None:
    """The Interval Enum and IntervalLiteral must enumerate the same set.

    Two sources of truth that must stay in sync — a frontend request using a
    valid IntervalLiteral must always map to a valid Interval enum and vice
    versa. This test fails fast on schema drift.
    """
    from typing import get_args

    from api.schemas import IntervalLiteral

    enum_values = {iv.value for iv in Interval}
    literal_values = set(get_args(IntervalLiteral))
    assert enum_values == literal_values, (
        f"Interval enum {sorted(enum_values)} != IntervalLiteral "
        f"{sorted(literal_values)} — schema drift between core and api"
    )


def test_kr_stock_intraday_interval_rejected(mocker, writable_tmp_dir) -> None:
    """`kr_stock` + sub-daily interval must fail validation before reaching the
    adapter (so it's a 4xx, not a 5xx)."""
    from core.types.errors import InvalidSymbolError

    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    krx_dl = mocker.patch("core.adapters.krx_adapter.download")

    for iv in (Interval.M1, Interval.M5, Interval.M15, Interval.H1, Interval.H4):
        req = FetchRequest(
            market=Market.KR_STOCK,
            symbol="005930",
            interval=iv,
            start=pd.Timestamp("2024-01-01"),
            end=pd.Timestamp("2024-01-10"),
        )
        with pytest.raises(InvalidSymbolError, match="not supported for KR stocks"):
            data_loader.fetch(req)

    assert krx_dl.call_count == 0, "krx adapter must never be called for unsupported intervals"


def test_subday_interval_cache_key_includes_time(mocker, writable_tmp_dir) -> None:
    """Two intraday requests on the same date but different times must hit
    distinct cache paths (regression: sub-day windows collided when the key was
    date-only)."""
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    mocker.patch("core.adapters.binance_adapter.download", return_value=fake)
    spy = mocker.spy(data_loader.cache, "ohlcv_cache_path")

    base = pd.Timestamp("2024-06-01T00:00:00")
    for hour_offset in (0, 6):
        req = FetchRequest(
            market=Market.CRYPTO,
            symbol="BTCUSDT",
            interval=Interval.M15,
            start=base + pd.Timedelta(hours=hour_offset),
            end=base + pd.Timedelta(hours=hour_offset + 2),
        )
        data_loader.fetch(req)

    assert spy.call_count == 2
    paths = {c.kwargs.get("start") for c in spy.call_args_list}
    assert len(paths) == 2, f"sub-day interval requests collided on cache key: {paths}"
