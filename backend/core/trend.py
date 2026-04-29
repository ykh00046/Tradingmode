"""Trend classification using ADX strength + MA alignment."""

from __future__ import annotations

import pandas as pd

from core.types.schemas import TrendState

DEFAULT_ADX_THRESHOLD: float = 25.0


def classify(
    df: pd.DataFrame,
    adx_threshold: float = DEFAULT_ADX_THRESHOLD,
    sma_short: int = 20,
    sma_mid: int = 60,
    sma_long: int = 120,
) -> TrendState:
    """Classify the trend at the most recent bar.

    Rules
    -----
    - If ADX <= threshold → SIDEWAYS (no clear trend, regardless of MA).
    - Else if SMA_short > SMA_mid > SMA_long → UPTREND.
    - Else if SMA_short < SMA_mid < SMA_long → DOWNTREND.
    - Otherwise → SIDEWAYS (mixed alignment).
    """
    if len(df) == 0:
        return TrendState.SIDEWAYS

    adx_col = "ADX_14"
    short_col = f"SMA_{sma_short}"
    mid_col = f"SMA_{sma_mid}"
    long_col = f"SMA_{sma_long}"

    needed = {adx_col, short_col, mid_col, long_col}
    if not needed.issubset(df.columns):
        return TrendState.SIDEWAYS

    last = df.iloc[-1]
    adx = last[adx_col]
    s, m, l = last[short_col], last[mid_col], last[long_col]

    if pd.isna(adx) or pd.isna(s) or pd.isna(m) or pd.isna(l):
        return TrendState.SIDEWAYS

    if adx <= adx_threshold:
        return TrendState.SIDEWAYS
    if s > m > l:
        return TrendState.UPTREND
    if s < m < l:
        return TrendState.DOWNTREND
    return TrendState.SIDEWAYS


def classify_series(
    df: pd.DataFrame,
    adx_threshold: float = DEFAULT_ADX_THRESHOLD,
    sma_short: int = 20,
    sma_mid: int = 60,
    sma_long: int = 120,
) -> pd.Series:
    """Classify the trend at every bar — returns a Series of ``TrendState`` values.

    Useful for backtesting: gives the historical evolution of the trend.
    """
    short_col = f"SMA_{sma_short}"
    mid_col = f"SMA_{sma_mid}"
    long_col = f"SMA_{sma_long}"
    adx_col = "ADX_14"

    needed = {adx_col, short_col, mid_col, long_col}
    if not needed.issubset(df.columns):
        return pd.Series([TrendState.SIDEWAYS] * len(df), index=df.index)

    adx = df[adx_col]
    s = df[short_col]
    m = df[mid_col]
    l = df[long_col]  # noqa: E741

    up = (adx > adx_threshold) & (s > m) & (m > l)
    down = (adx > adx_threshold) & (s < m) & (m < l)

    out = pd.Series([TrendState.SIDEWAYS] * len(df), index=df.index, dtype=object)
    out[up.fillna(False)] = TrendState.UPTREND
    out[down.fillna(False)] = TrendState.DOWNTREND
    return out
