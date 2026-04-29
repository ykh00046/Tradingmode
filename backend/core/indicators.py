"""Technical indicators — pandas-ta wrappers.

All functions take a DataFrame with columns ``open, high, low, close, volume``
indexed by ``DatetimeIndex`` and return a new DataFrame with the indicator
columns appended. The original DataFrame is never mutated.
"""

from __future__ import annotations

from typing import cast

import pandas as pd
import pandas_ta as ta

from core.types.errors import InsufficientDataError
from core.types.schemas import IndicatorConfig

# =============================================================================
# Defaults
# =============================================================================

DEFAULT_SMA_PERIODS: list[int] = [5, 20, 60, 120]
DEFAULT_RSI_PERIOD: int = 14
DEFAULT_MACD: tuple[int, int, int] = (12, 26, 9)
DEFAULT_BBANDS: tuple[int, float] = (20, 2.0)
DEFAULT_ADX_LENGTH: int = 14


# =============================================================================
# Validation
# =============================================================================


def _validate_ohlcv(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise InsufficientDataError(
            f"OHLCV columns missing: {sorted(missing)}",
            details={"available": list(df.columns)},
        )


def _ensure_min_length(df: pd.DataFrame, required: int, indicator: str) -> None:
    if len(df) < required:
        raise InsufficientDataError(
            f"{indicator} requires at least {required} bars, got {len(df)}",
            details={"required": required, "actual": len(df), "indicator": indicator},
        )


# =============================================================================
# Individual indicator functions
# =============================================================================


def add_sma(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """Append simple moving averages as ``SMA_<period>`` columns."""
    out = df.copy()
    periods = periods or DEFAULT_SMA_PERIODS
    _ensure_min_length(out, max(periods), "SMA")
    for p in periods:
        out[f"SMA_{p}"] = ta.sma(out["close"], length=p)
    return out


def add_ema(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """Append exponential moving averages.

    v0.4 keeps EMA(12, 26) only, used internally by MACD. Chart EMA overlays
    are deferred to v2.
    """
    out = df.copy()
    _ensure_min_length(out, max(periods), "EMA")
    for p in periods:
        out[f"EMA_{p}"] = ta.ema(out["close"], length=p)
    return out


def add_rsi(df: pd.DataFrame, period: int = DEFAULT_RSI_PERIOD) -> pd.DataFrame:
    """Append ``RSI_<period>`` column."""
    out = df.copy()
    _ensure_min_length(out, period + 1, "RSI")
    out[f"RSI_{period}"] = ta.rsi(out["close"], length=period)
    return out


def add_macd(
    df: pd.DataFrame,
    fast: int = DEFAULT_MACD[0],
    slow: int = DEFAULT_MACD[1],
    signal: int = DEFAULT_MACD[2],
) -> pd.DataFrame:
    """Append MACD columns: ``MACD_<f>_<s>_<sig>``, ``MACDh_...``, ``MACDs_...``."""
    out = df.copy()
    _ensure_min_length(out, slow + signal, "MACD")
    macd_df = cast(pd.DataFrame, ta.macd(out["close"], fast=fast, slow=slow, signal=signal))
    out = out.join(macd_df)
    return out


def add_bbands(
    df: pd.DataFrame,
    length: int = DEFAULT_BBANDS[0],
    std: float = DEFAULT_BBANDS[1],
) -> pd.DataFrame:
    """Append Bollinger Bands columns: ``BBL_<l>_<s>``, ``BBM_...``, ``BBU_...``."""
    out = df.copy()
    _ensure_min_length(out, length, "BBANDS")
    bb_df = cast(pd.DataFrame, ta.bbands(out["close"], length=length, std=std))
    out = out.join(bb_df)
    return out


def add_adx(df: pd.DataFrame, length: int = DEFAULT_ADX_LENGTH) -> pd.DataFrame:
    """Append ADX columns: ``ADX_<l>``, ``DMP_<l>``, ``DMN_<l>``."""
    out = df.copy()
    _ensure_min_length(out, length * 2, "ADX")
    adx_df = cast(
        pd.DataFrame,
        ta.adx(out["high"], out["low"], out["close"], length=length),
    )
    out = out.join(adx_df)
    return out


# =============================================================================
# Bulk computation
# =============================================================================


def compute(df: pd.DataFrame, config: IndicatorConfig | None = None) -> pd.DataFrame:
    """Append all indicators to a copy of ``df``.

    Returns a new DataFrame with the original columns plus:
        SMA_5, SMA_20, SMA_60, SMA_120
        RSI_14
        MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
        BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
        ADX_14, DMP_14, DMN_14
    """
    _validate_ohlcv(df)
    cfg = config or {}

    out = df.copy()
    out = add_sma(out, cfg.get("sma_periods", DEFAULT_SMA_PERIODS))
    out = add_rsi(out, cfg.get("rsi_period", DEFAULT_RSI_PERIOD))

    fast, slow, signal = cfg.get("macd", DEFAULT_MACD)
    out = add_macd(out, fast=fast, slow=slow, signal=signal)

    bb_len, bb_std = cfg.get("bbands", DEFAULT_BBANDS)
    out = add_bbands(out, length=bb_len, std=bb_std)

    out = add_adx(out, length=cfg.get("adx_length", DEFAULT_ADX_LENGTH))

    return out
