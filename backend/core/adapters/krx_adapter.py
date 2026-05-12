"""Korean stock OHLCV adapter (KOSPI / KOSDAQ).

Uses ``pykrx`` for daily OHLCV. ``FinanceDataReader`` is used as a fallback /
secondary source for tickers pykrx returns empty for. Intraday data is not
supported in v0.4 (deferred to v2 — see Plan §5 Risks).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.types.errors import DataSourceError, InvalidSymbolError
from lib.logger import get_logger

log = get_logger(__name__)


def _import_pykrx() -> Any:
    try:
        from pykrx import stock                                              # type: ignore
        return stock
    except ImportError as e:                                                # pragma: no cover
        raise DataSourceError("pykrx is not installed") from e


def _import_fdr() -> Any:
    try:
        import FinanceDataReader as fdr                                      # type: ignore
        return fdr
    except ImportError as e:                                                # pragma: no cover
        raise DataSourceError("FinanceDataReader is not installed") from e


# Supported intervals: 1d (native daily) + 1w/1M (resampled from daily).
# Intraday (1m/5m/15m/1h/4h) is not supported for KR stocks (deferred to v2).
_INTERVAL_TO_FREQ = {
    "1w": "W-FRI",   # weekly, Friday close (matches KR market close)
    "1M": "ME",      # month-end (pandas 2.x; deprecated 'M' triggers FutureWarning)
}
_SUPPORTED_INTERVALS = {"1d", "1w", "1M"}
# Extra daily lookback (in calendar days) needed for clean resample boundaries.
_RESAMPLE_BUFFER_DAYS = {"1w": 70, "1M": 350}
# Minimum daily rows required to form a meaningful resample bucket.
# (5 = one full Mon–Fri week; 15 = ~half a trading month, conservative monthly floor.)
# Newly-listed stocks below these thresholds get a clear error instead of a
# misleading partial-period bar.
_MIN_DAILY_FOR_INTERVAL = {"1w": 5, "1M": 15}


def _ensure_supported_interval(interval: str) -> None:
    if interval not in _SUPPORTED_INTERVALS:
        raise DataSourceError(
            f"KR stock adapter does not support '{interval}' "
            f"(supported: {sorted(_SUPPORTED_INTERVALS)})",
            details={"interval": interval},
        )


def _resample_ohlcv(daily_df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate daily OHLCV into a coarser frequency (weekly / monthly).

    Parameters
    ----------
    daily_df : DataFrame with DatetimeIndex and columns
        ``['open', 'high', 'low', 'close', 'volume']``.
    freq : pandas resample frequency string (e.g. ``'W-FRI'``, ``'ME'``).

    Returns
    -------
    DataFrame with the same column shape, indexed by the period-end timestamp.
    Empty periods (no trading days) are dropped via ``dropna(subset=['close'])``.
    """
    if daily_df.empty:
        return daily_df

    agg = daily_df.resample(freq).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return agg.dropna(subset=["close"])


_PYKRX_COLUMN_MAP = {
    "시가": "open",
    "고가": "high",
    "저가": "low",
    "종가": "close",
    "거래량": "volume",
}


def _try_pykrx(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    stock = _import_pykrx()
    df = stock.get_market_ohlcv(start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), symbol)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=_PYKRX_COLUMN_MAP)
    keep = ["open", "high", "low", "close", "volume"]
    df = df[keep].astype(float)
    df.index = pd.to_datetime(df.index)
    df.index.name = "timestamp"
    return df


def _try_fdr(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    fdr = _import_fdr()
    df = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=str.lower)
    keep = ["open", "high", "low", "close", "volume"]
    df = df[keep].astype(float)
    df.index = pd.to_datetime(df.index)
    df.index.name = "timestamp"
    return df


def download(
    symbol: str,
    interval: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Fetch KR stock OHLCV (daily / weekly / monthly).

    For ``interval='1d'`` returns the raw daily series. For ``'1w'`` / ``'1M'``
    fetches an extended daily window (with ``_RESAMPLE_BUFFER_DAYS`` buffer)
    and resamples via pandas. Caches the resampled output, not the daily input.

    Tries pykrx first, falls back to FinanceDataReader. Both empty → InvalidSymbolError.
    """
    _ensure_supported_interval(interval)
    log.info("krx fetch: %s %s %s..%s", symbol, interval, start, end)

    # Extend lookback for resample to absorb partial-period boundaries.
    if interval == "1d":
        daily_start = start
    else:
        daily_start = start - pd.Timedelta(days=_RESAMPLE_BUFFER_DAYS[interval])

    try:
        df = _try_pykrx(symbol, daily_start, end)
        if df.empty:
            log.info("pykrx returned empty for %s, trying FinanceDataReader", symbol)
            df = _try_fdr(symbol, daily_start, end)
        if df.empty:
            raise InvalidSymbolError(f"no data for KR symbol: {symbol}")

        if interval == "1d":
            return df

        # Minimum-bars guard: real protection against newly-listed symbols.
        # Without this, 3 daily rows would still produce 1 partial weekly bar
        # that leaks misleading data to the chart (Gap M-1 in v0.8 analysis).
        min_daily = _MIN_DAILY_FOR_INTERVAL[interval]
        if len(df) < min_daily:
            raise DataSourceError(
                f"insufficient daily data for {interval} resample: "
                f"{symbol} has {len(df)} daily rows (need at least {min_daily})",
                details={
                    "symbol": symbol,
                    "interval": interval,
                    "daily_rows": len(df),
                    "min_required": min_daily,
                },
            )

        resampled = _resample_ohlcv(df, _INTERVAL_TO_FREQ[interval])
        if resampled.empty:
            # Defensive: even with min_daily met, if all closes are NaN the
            # dropna(close) inside _resample_ohlcv yields zero rows.
            raise DataSourceError(
                f"insufficient daily data for {interval} resample: "
                f"{symbol} ({len(df)} daily rows, all-NaN closes)",
                details={
                    "symbol": symbol,
                    "interval": interval,
                    "daily_rows": len(df),
                },
            )
        # Trim buffer rows that fall before the requested start.
        return resampled[resampled.index >= start]

    except (InvalidSymbolError, DataSourceError):
        raise
    except Exception as e:                                                    # pragma: no cover
        raise DataSourceError(
            f"KR adapter failed: {e}",
            details={
                "symbol": symbol,
                "type": type(e).__name__,
                "interval": interval,
            },
        ) from e
