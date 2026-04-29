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


def _ensure_daily(interval: str) -> None:
    if interval != "1d":
        raise DataSourceError(
            f"KR stock adapter only supports daily ('1d'), got '{interval}' (intraday is v2)",
            details={"interval": interval},
        )


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
    """Fetch KR stock daily OHLCV.

    Tries pykrx first, falls back to FinanceDataReader. Both empty → InvalidSymbolError.
    """
    _ensure_daily(interval)
    log.info("krx fetch: %s %s %s..%s", symbol, interval, start, end)

    try:
        df = _try_pykrx(symbol, start, end)
        if not df.empty:
            return df

        log.info("pykrx returned empty for %s, trying FinanceDataReader", symbol)
        df = _try_fdr(symbol, start, end)
        if not df.empty:
            return df

        raise InvalidSymbolError(f"no data for KR symbol: {symbol}")
    except (InvalidSymbolError, DataSourceError):
        raise
    except Exception as e:                                                    # pragma: no cover
        raise DataSourceError(
            f"KR adapter failed: {e}",
            details={"symbol": symbol, "type": type(e).__name__},
        ) from e
