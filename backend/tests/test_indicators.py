"""Unit tests for ``core.indicators``."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from core import indicators
from core.types.errors import InsufficientDataError


# =============================================================================
# Validation
# =============================================================================


def test_compute_raises_on_missing_columns() -> None:
    df = pd.DataFrame({"close": [1.0, 2.0]}, index=pd.date_range("2024-01-01", periods=2))
    with pytest.raises(InsufficientDataError) as exc:
        indicators.compute(df)
    assert "missing" in str(exc.value).lower()


def test_add_sma_raises_when_too_short(short_df: pd.DataFrame) -> None:
    with pytest.raises(InsufficientDataError):
        indicators.add_sma(short_df, periods=[120])


# =============================================================================
# SMA
# =============================================================================


def test_add_sma_known_values(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_sma(trending_up_df, periods=[5])
    expected = trending_up_df["close"].rolling(window=5).mean()
    pd.testing.assert_series_equal(
        out["SMA_5"].dropna(),
        expected.dropna(),
        check_names=False,
        atol=1e-9,
    )


def test_add_sma_does_not_mutate_input(trending_up_df: pd.DataFrame) -> None:
    cols_before = list(trending_up_df.columns)
    indicators.add_sma(trending_up_df, periods=[20])
    assert list(trending_up_df.columns) == cols_before


# =============================================================================
# RSI
# =============================================================================


def test_add_rsi_in_valid_range(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_rsi(trending_up_df, period=14)
    rsi = out["RSI_14"].dropna()
    assert (rsi >= 0).all() and (rsi <= 100).all()


def test_add_rsi_uptrend_above_50(trending_up_df: pd.DataFrame) -> None:
    """A persistent uptrend should keep RSI mostly above 50."""
    out = indicators.add_rsi(trending_up_df)
    rsi = out["RSI_14"].dropna()
    assert (rsi > 50).mean() > 0.7   # at least 70% of bars above 50


# =============================================================================
# MACD
# =============================================================================


def test_add_macd_columns(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_macd(trending_up_df)
    assert "MACD_12_26_9" in out.columns
    assert "MACDs_12_26_9" in out.columns
    assert "MACDh_12_26_9" in out.columns


# =============================================================================
# Bollinger Bands
# =============================================================================


def test_add_bbands_ordering(trending_up_df: pd.DataFrame) -> None:
    """For every bar with valid bands: lower <= middle <= upper."""
    out = indicators.add_bbands(trending_up_df)
    bbl, bbm, bbu = "BBL_20_2.0_2.0", "BBM_20_2.0_2.0", "BBU_20_2.0_2.0"
    valid = out[[bbl, bbm, bbu]].dropna()
    assert (valid[bbl] <= valid[bbm]).all()
    assert (valid[bbm] <= valid[bbu]).all()


# =============================================================================
# ADX
# =============================================================================


def test_add_adx_in_valid_range(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_adx(trending_up_df)
    adx = out["ADX_14"].dropna()
    assert (adx >= 0).all() and (adx <= 100).all()


def test_adx_higher_in_trend_than_in_chop(
    trending_up_df: pd.DataFrame,
    sideways_df: pd.DataFrame,
) -> None:
    """ADX should be markedly higher in a trending market than in a choppy one."""
    trend_adx = indicators.add_adx(trending_up_df)["ADX_14"].dropna().mean()
    chop_adx = indicators.add_adx(sideways_df)["ADX_14"].dropna().mean()
    assert trend_adx > chop_adx


# =============================================================================
# Bulk compute
# =============================================================================


def test_compute_appends_all_columns(trending_up_df: pd.DataFrame) -> None:
    out = indicators.compute(trending_up_df)
    expected = {
        "SMA_5", "SMA_20", "SMA_60", "SMA_120",
        "RSI_14",
        "MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9",
        # pandas-ta 0.4.x emits BB names with the std value duplicated
        "BBL_20_2.0_2.0", "BBM_20_2.0_2.0", "BBU_20_2.0_2.0",
        "ADX_14", "DMP_14", "DMN_14",
    }
    assert expected.issubset(set(out.columns))


def test_compute_preserves_ohlcv(trending_up_df: pd.DataFrame) -> None:
    out = indicators.compute(trending_up_df)
    for col in ("open", "high", "low", "close", "volume"):
        pd.testing.assert_series_equal(out[col], trending_up_df[col])


def test_compute_with_custom_config(trending_up_df: pd.DataFrame) -> None:
    out = indicators.compute(
        trending_up_df,
        config={"sma_periods": [10], "rsi_period": 7},
    )
    assert "SMA_10" in out.columns
    assert "RSI_7" in out.columns
    # Defaults that were not overridden still apply
    assert "MACD_12_26_9" in out.columns

    # And periods that were overridden away should NOT be present
    assert "SMA_20" not in out.columns
    assert "RSI_14" not in out.columns


# =============================================================================
# Determinism
# =============================================================================


def test_compute_is_deterministic(trending_up_df: pd.DataFrame) -> None:
    out1 = indicators.compute(trending_up_df)
    out2 = indicators.compute(trending_up_df)
    pd.testing.assert_frame_equal(out1, out2)


# =============================================================================
# RSI Price Band (RPB) — v0.6.0
# =============================================================================


_RPB_UPPER_COLS = {"RPB_UP_70", "RPB_UP_75", "RPB_UP_80"}
_RPB_LOWER_COLS = {"RPB_DN_30", "RPB_DN_25", "RPB_DN_20"}
_RPB_BARS_COLS = {f"{c}_BARS" for c in (_RPB_UPPER_COLS | _RPB_LOWER_COLS)}


def test_add_rpb_creates_all_12_columns(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_rpb(trending_up_df)
    expected = _RPB_UPPER_COLS | _RPB_LOWER_COLS | _RPB_BARS_COLS
    assert expected.issubset(set(out.columns))
    # Datatype: every column must be float
    for col in expected:
        assert out[col].dtype == float, f"{col} dtype must be float64"


def test_add_rpb_empty_lists_skips_all_columns(trending_up_df: pd.DataFrame) -> None:
    """Both sides empty → 12 RPB columns omitted, but other columns intact."""
    cols_before = set(trending_up_df.columns)
    out = indicators.add_rpb(trending_up_df, upper=[], lower=[])
    rpb_added = set(out.columns) - cols_before
    assert not any(c.startswith("RPB_") for c in rpb_added)


def test_add_rpb_one_side_empty_only_other_side_emitted(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_rpb(trending_up_df, upper=[70], lower=[])
    assert "RPB_UP_70" in out.columns and "RPB_UP_70_BARS" in out.columns
    assert not any(c.startswith("RPB_DN_") for c in out.columns)


def test_add_rpb_silently_filters_invalid_thresholds(trending_up_df: pd.DataFrame) -> None:
    """Upper ≤ 50 and lower ≥ 50 are dropped silently."""
    out = indicators.add_rpb(trending_up_df, upper=[40, 70, 100], lower=[10, 30, 80])
    assert "RPB_UP_40" not in out.columns       # ≤ 50 → dropped
    assert "RPB_UP_100" not in out.columns      # >= 100 → dropped
    assert "RPB_UP_70" in out.columns           # valid
    assert "RPB_DN_80" not in out.columns       # >= 50 → dropped
    assert "RPB_DN_30" in out.columns           # valid


def test_add_rpb_bars_signs(trending_up_df: pd.DataFrame) -> None:
    """Upper BARS strictly positive (or NaN), lower BARS strictly negative (or NaN)."""
    out = indicators.add_rpb(trending_up_df)
    for col in ("RPB_UP_70_BARS", "RPB_UP_75_BARS", "RPB_UP_80_BARS"):
        valid = out[col].dropna()
        assert (valid > 0).all(), f"{col} should be positive on valid rows"
    for col in ("RPB_DN_30_BARS", "RPB_DN_25_BARS", "RPB_DN_20_BARS"):
        valid = out[col].dropna()
        assert (valid < 0).all(), f"{col} should be negative on valid rows"


def test_add_rpb_lower_prices_strictly_positive(trending_up_df: pd.DataFrame) -> None:
    """RS Cap + price > 0 guard ensure no negative or zero lower-band price."""
    out = indicators.add_rpb(trending_up_df)
    for col in _RPB_LOWER_COLS:
        valid = out[col].dropna()
        assert (valid > 0).all(), f"{col} contains non-positive prices"


def test_add_rpb_upper_above_close(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_rpb(trending_up_df)
    close = out["close"]
    for col in _RPB_UPPER_COLS:
        diff = (out[col] - close).dropna()
        assert (diff > 0).all(), f"{col} must be above close"


def test_add_rpb_atr_filter_clamps_far_prices(trending_up_df: pd.DataFrame) -> None:
    """A tiny atr_mult should NaN almost all band rows (target unreachable)."""
    out = indicators.add_rpb(trending_up_df, atr_mult=0.001)
    for col in _RPB_UPPER_COLS | _RPB_LOWER_COLS:
        nan_ratio = out[col].isna().mean()
        assert nan_ratio > 0.95, f"{col} should be mostly NaN with atr_mult=0.001"


def test_add_rpb_short_input_raises_insufficient_data(short_df: pd.DataFrame) -> None:
    """Default needs 2N = 28 bars; ``short_df`` has 50 bars so it passes — use a
    shorter slice to trigger the guard explicitly."""
    tiny = short_df.iloc[:20].copy()                                          # < 28
    with pytest.raises(InsufficientDataError):
        indicators.add_rpb(tiny)


def test_add_rpb_is_deterministic(trending_up_df: pd.DataFrame) -> None:
    a = indicators.add_rpb(trending_up_df)
    b = indicators.add_rpb(trending_up_df)
    pd.testing.assert_frame_equal(a, b)


def test_add_rpb_preserves_input_columns(trending_up_df: pd.DataFrame) -> None:
    out = indicators.add_rpb(trending_up_df)
    for col in trending_up_df.columns:
        pd.testing.assert_series_equal(out[col], trending_up_df[col])


def test_compute_includes_rpb_by_default(trending_up_df: pd.DataFrame) -> None:
    out = indicators.compute(trending_up_df)
    expected = _RPB_UPPER_COLS | _RPB_LOWER_COLS | _RPB_BARS_COLS
    assert expected.issubset(set(out.columns))


def test_compute_disables_rpb_when_both_lists_empty(trending_up_df: pd.DataFrame) -> None:
    out = indicators.compute(
        trending_up_df, config={"rpb_upper": [], "rpb_lower": []},
    )
    assert not any(c.startswith("RPB_") for c in out.columns)


def test_compute_passes_through_rpb_custom_thresholds(trending_up_df: pd.DataFrame) -> None:
    out = indicators.compute(
        trending_up_df, config={"rpb_upper": [65], "rpb_lower": [35]},
    )
    assert "RPB_UP_65" in out.columns
    assert "RPB_DN_35" in out.columns
    assert "RPB_UP_70" not in out.columns       # default overridden away
    assert "RPB_DN_30" not in out.columns


def test_add_rpb_forward_simulation_close_to_target(sideways_df: pd.DataFrame) -> None:
    """If we simulate "next bar closes at RPB_UP_70" and recompute RSI, the
    result should land near 70. Pine 단순화 채택으로 정밀도는 ε 수준이지만,
    방향성(>50 으로 상승)은 보장되어야 한다.

    Sideways 데이터를 쓰는 이유: 강한 추세에서는 ``avg_loss == 0`` 또는
    이미 RSI > 70 상태라 valid RPB_UP_70 행이 거의 안 나옴.
    """
    df = indicators.compute(sideways_df)
    valid_idx = df["RPB_UP_70"].dropna().index
    assert len(valid_idx) > 30, f"Need valid bars to forward-simulate, got {len(valid_idx)}"

    # Walk through several pivots and take the median resulting RSI — single-bar
    # noise is normal under the Pine n-1 단순화.
    new_rsis: list[float] = []
    for pivot in valid_idx[-20:]:
        predicted = df.at[pivot, "RPB_UP_70"]
        next_idx = pivot + pd.Timedelta(days=1)
        new_row = pd.DataFrame(
            {
                "open": [df.at[pivot, "close"]],
                "high": [predicted],
                "low": [df.at[pivot, "close"]],
                "close": [predicted],
                "volume": [df.at[pivot, "volume"]],
            },
            index=[next_idx],
        )
        # Slice up to and including the pivot, then append the synthetic bar.
        truncated = sideways_df.loc[:pivot]
        extended = pd.concat([truncated, new_row])
        new_rsi = indicators.add_rsi(extended)["RSI_14"].iloc[-1]
        new_rsis.append(float(new_rsi))

    median_rsi = float(np.median(new_rsis))
    # Pine 단순화로 정확히 70은 아니지만 60 ~ 80 사이여야 한다.
    assert 60 <= median_rsi <= 80, (
        f"median forward-simulated RSI = {median_rsi:.2f} (samples={new_rsis[:5]}...)"
    )
