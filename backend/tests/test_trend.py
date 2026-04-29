"""Unit tests for ``core.trend``."""

from __future__ import annotations

import pandas as pd

from core import indicators, trend
from core.types.schemas import TrendState


def test_classify_returns_uptrend_for_strong_uptrend(trending_up_df: pd.DataFrame) -> None:
    df = indicators.compute(trending_up_df)
    assert trend.classify(df) == TrendState.UPTREND


def test_classify_returns_downtrend_for_strong_downtrend(
    trending_down_df: pd.DataFrame,
) -> None:
    df = indicators.compute(trending_down_df)
    assert trend.classify(df) == TrendState.DOWNTREND


def test_classify_returns_sideways_for_chop(sideways_df: pd.DataFrame) -> None:
    df = indicators.compute(sideways_df)
    assert trend.classify(df) == TrendState.SIDEWAYS


def test_classify_returns_sideways_when_indicators_missing(
    trending_up_df: pd.DataFrame,
) -> None:
    # No indicators added — function must not crash, and should default to SIDEWAYS.
    assert trend.classify(trending_up_df) == TrendState.SIDEWAYS


def test_classify_respects_high_adx_threshold(trending_up_df: pd.DataFrame) -> None:
    df = indicators.compute(trending_up_df)
    # If we set a near-impossible threshold, even a strong trend → SIDEWAYS.
    assert trend.classify(df, adx_threshold=99.0) == TrendState.SIDEWAYS


def test_classify_handles_empty_df() -> None:
    empty = pd.DataFrame(
        {"open": [], "high": [], "low": [], "close": [], "volume": []},
        index=pd.DatetimeIndex([]),
    )
    assert trend.classify(empty) == TrendState.SIDEWAYS


def test_classify_series_length_matches_input(trending_up_df: pd.DataFrame) -> None:
    df = indicators.compute(trending_up_df)
    series = trend.classify_series(df)
    assert len(series) == len(df)


def test_classify_series_only_emits_known_states(trending_up_df: pd.DataFrame) -> None:
    df = indicators.compute(trending_up_df)
    series = trend.classify_series(df)
    states = set(series.unique())
    assert states.issubset({TrendState.UPTREND, TrendState.DOWNTREND, TrendState.SIDEWAYS})


def test_classify_is_deterministic(trending_up_df: pd.DataFrame) -> None:
    df = indicators.compute(trending_up_df)
    assert trend.classify(df) == trend.classify(df)
