"""Technical indicators implemented with pandas only.

All functions take a DataFrame with columns ``open, high, low, close, volume``
indexed by ``DatetimeIndex`` and return a new DataFrame with indicator columns
appended. The original DataFrame is never mutated.
"""

from __future__ import annotations

import pandas as pd

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


def _wilder_ewm(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def _bb_col(prefix: str, length: int, std: float) -> str:
    std_str = f"{float(std):.1f}"
    return f"{prefix}_{length}_{std_str}_{std_str}"


# =============================================================================
# Individual indicator functions
# =============================================================================


def add_sma(df: pd.DataFrame, periods: list[int] | None = None) -> pd.DataFrame:
    """Append simple moving averages as ``SMA_<period>`` columns."""
    out = df.copy()
    periods = periods or DEFAULT_SMA_PERIODS
    _ensure_min_length(out, max(periods), "SMA")
    for p in periods:
        out[f"SMA_{p}"] = out["close"].rolling(window=p, min_periods=p).mean()
    return out


def add_ema(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """Append exponential moving averages."""
    out = df.copy()
    _ensure_min_length(out, max(periods), "EMA")
    for p in periods:
        out[f"EMA_{p}"] = out["close"].ewm(span=p, adjust=False, min_periods=p).mean()
    return out


def add_rsi(df: pd.DataFrame, period: int = DEFAULT_RSI_PERIOD) -> pd.DataFrame:
    """Append ``RSI_<period>`` column using Wilder smoothing."""
    out = df.copy()
    _ensure_min_length(out, period + 1, "RSI")

    delta = out["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = _wilder_ewm(gain, period)
    avg_loss = _wilder_ewm(loss, period)
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    out[f"RSI_{period}"] = rsi.where(avg_loss != 0, 100.0)
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

    ema_fast = out["close"].ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = out["close"].ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    hist = macd_line - signal_line

    suffix = f"{fast}_{slow}_{signal}"
    out[f"MACD_{suffix}"] = macd_line
    out[f"MACDs_{suffix}"] = signal_line
    out[f"MACDh_{suffix}"] = hist
    return out


def add_bbands(
    df: pd.DataFrame,
    length: int = DEFAULT_BBANDS[0],
    std: float = DEFAULT_BBANDS[1],
) -> pd.DataFrame:
    """Append Bollinger Bands columns using population std-dev."""
    out = df.copy()
    _ensure_min_length(out, length, "BBANDS")

    mid = out["close"].rolling(window=length, min_periods=length).mean()
    sigma = out["close"].rolling(window=length, min_periods=length).std(ddof=0)
    out[_bb_col("BBL", length, std)] = mid - sigma * std
    out[_bb_col("BBM", length, std)] = mid
    out[_bb_col("BBU", length, std)] = mid + sigma * std
    return out


def add_adx(df: pd.DataFrame, length: int = DEFAULT_ADX_LENGTH) -> pd.DataFrame:
    """Append ADX columns: ``ADX_<l>``, ``DMP_<l>``, ``DMN_<l>``."""
    out = df.copy()
    _ensure_min_length(out, length * 2, "ADX")

    high = out["high"]
    low = out["low"]
    close = out["close"]

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = pd.concat(
        [
            (high - low),
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = _wilder_ewm(tr, length)

    plus_di = 100 * _wilder_ewm(plus_dm, length) / atr.replace(0, pd.NA)
    minus_di = 100 * _wilder_ewm(minus_dm, length) / atr.replace(0, pd.NA)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)
    adx = _wilder_ewm(dx, length)

    out[f"ADX_{length}"] = adx
    out[f"DMP_{length}"] = plus_di
    out[f"DMN_{length}"] = minus_di
    return out


# =============================================================================
# Bulk computation
# =============================================================================


def compute(df: pd.DataFrame, config: IndicatorConfig | None = None) -> pd.DataFrame:
    """Append all indicators to a copy of ``df``."""
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
