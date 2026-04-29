"""Unit tests for ``core.signals``."""

from __future__ import annotations

import pandas as pd

from core import indicators, signals
from core.types.schemas import SignalAction, SignalKind


def test_detect_ma_cross_finds_golden_cross(golden_cross_df: pd.DataFrame) -> None:
    df = indicators.add_sma(golden_cross_df, periods=[20, 60])
    found = signals.detect_ma_cross(df, short=20, long=60)
    golden = [s for s in found if s.kind == SignalKind.GOLDEN_CROSS]
    assert len(golden) >= 1
    assert all(s.action == SignalAction.BUY for s in golden)


def test_detect_ma_cross_finds_death_cross(death_cross_df: pd.DataFrame) -> None:
    df = indicators.add_sma(death_cross_df, periods=[20, 60])
    found = signals.detect_ma_cross(df, short=20, long=60)
    death = [s for s in found if s.kind == SignalKind.DEATH_CROSS]
    assert len(death) >= 1
    assert all(s.action == SignalAction.SELL for s in death)


def test_detect_ma_cross_returns_empty_when_columns_missing(
    trending_up_df: pd.DataFrame,
) -> None:
    # No SMA columns added — should return [] gracefully.
    assert signals.detect_ma_cross(trending_up_df, short=20, long=60) == []


def test_detect_rsi_signals_triggers_in_volatile_market(
    death_cross_df: pd.DataFrame,
) -> None:
    """A series that rises then falls sharply should produce at least one RSI signal."""
    df = indicators.add_rsi(death_cross_df)
    found = signals.detect_rsi_signals(df)
    assert len(found) >= 1


def test_detect_rsi_divergence_returns_empty_when_too_short(
    short_df: pd.DataFrame,
) -> None:
    df = short_df.copy()
    df["RSI_14"] = 50.0
    assert signals.detect_rsi_divergence(df, period=14, lookback=20) == []


def test_detect_macd_cross_runs_without_errors(trending_up_df: pd.DataFrame) -> None:
    df = indicators.add_macd(trending_up_df)
    found = signals.detect_macd_cross(df)
    # Just make sure it runs and returns some signals or empty list
    assert isinstance(found, list)


def test_detect_all_returns_sorted_by_timestamp(golden_cross_df: pd.DataFrame) -> None:
    df = indicators.compute(golden_cross_df)
    found = signals.detect_all(df)
    timestamps = [s.timestamp for s in found]
    assert timestamps == sorted(timestamps)


def test_detect_all_returns_empty_on_empty_indicators() -> None:
    """When the DataFrame has no indicator columns, detect_all returns []."""
    empty_df = pd.DataFrame(
        {"open": [], "high": [], "low": [], "close": [], "volume": []},
        index=pd.DatetimeIndex([]),
    )
    assert signals.detect_all(empty_df) == []


def test_signal_strength_is_one_in_v04(golden_cross_df: pd.DataFrame) -> None:
    """v0.4 fixes strength=1.0; per-kind formulas land in v2."""
    df = indicators.compute(golden_cross_df)
    for s in signals.detect_all(df):
        assert s.strength == 1.0


def test_detection_is_deterministic(golden_cross_df: pd.DataFrame) -> None:
    df = indicators.compute(golden_cross_df)
    a = signals.detect_all(df)
    b = signals.detect_all(df)
    assert a == b
