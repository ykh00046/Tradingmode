"""Unit tests for ``core.indicators``."""

from __future__ import annotations

import math

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
    valid = out[["BBL_20_2.0", "BBM_20_2.0", "BBU_20_2.0"]].dropna()
    assert (valid["BBL_20_2.0"] <= valid["BBM_20_2.0"]).all()
    assert (valid["BBM_20_2.0"] <= valid["BBU_20_2.0"]).all()


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
        "BBL_20_2.0", "BBM_20_2.0", "BBU_20_2.0",
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
