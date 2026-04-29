"""Binance Spot OHLCV adapter.

Wraps ``python-binance`` and translates errors into our domain exceptions.
The public API is a single function ``download`` so call sites stay simple.

Authentication is optional: public market data works without API keys.
When ``BINANCE_API_KEY`` / ``BINANCE_API_SECRET`` are set, rate limits are
slightly higher and the same Client instance can be reused for trading later.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

from core.types.errors import DataSourceError, InvalidSymbolError
from lib.logger import get_logger

log = get_logger(__name__)


# Binance kline interval string mapping (matches Interval enum values)
_INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def _client() -> Any:
    """Lazy-construct a python-binance Client.

    Imported lazily so that environments without ``python-binance`` installed
    can still import this module (the function is only invoked when fetching).
    """
    try:
        from binance.client import Client
    except ImportError as e:                                                # pragma: no cover
        raise DataSourceError("python-binance is not installed") from e

    api_key = os.environ.get("BINANCE_API_KEY") or None
    api_secret = os.environ.get("BINANCE_API_SECRET") or None
    return Client(api_key=api_key, api_secret=api_secret)


def _to_milliseconds(ts: pd.Timestamp) -> int:
    return int(ts.timestamp() * 1000)


def _normalize(klines: list[list[Any]]) -> pd.DataFrame:
    """Convert Binance raw kline lists to an OHLCV DataFrame indexed by UTC time."""
    if not klines:
        return pd.DataFrame(
            {"open": [], "high": [], "low": [], "close": [], "volume": []},
            index=pd.DatetimeIndex([], tz="UTC", name="timestamp"),
        )
    rows = [
        {
            "timestamp": pd.Timestamp(k[0], unit="ms", tz="UTC"),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
        for k in klines
    ]
    df = pd.DataFrame(rows).set_index("timestamp")
    return df


def download(
    symbol: str,
    interval: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Fetch Binance Spot klines and return an OHLCV DataFrame.

    Raises
    ------
    InvalidSymbolError
        Unknown symbol on Binance.
    DataSourceError
        Network / auth / rate-limit failure. Sets ``rate_limit=True`` when the
        API responded with HTTP 429 so callers can map to the right HTTP code.
    """
    if interval not in _INTERVAL_MAP:
        raise DataSourceError(
            f"unsupported Binance interval: {interval}",
            details={"interval": interval},
        )

    log.info("binance fetch: %s %s %s..%s", symbol, interval, start, end)

    try:
        client = _client()
        klines = client.get_historical_klines(
            symbol,
            _INTERVAL_MAP[interval],
            start_str=_to_milliseconds(start),
            end_str=_to_milliseconds(end),
        )
    except Exception as e:
        message = str(e)
        # python-binance raises BinanceAPIException; check by message rather
        # than importing the class to keep this module decoupled.
        cls_name = type(e).__name__
        if "Invalid symbol" in message or "INVALID" in message.upper() and "SYMBOL" in message.upper():
            raise InvalidSymbolError(f"unknown Binance symbol: {symbol}") from e
        if "429" in message or "Too many requests" in message or "rate limit" in message.lower():
            raise DataSourceError(
                f"Binance rate limit hit: {message}",
                rate_limit=True,
                details={"symbol": symbol, "type": cls_name},
            ) from e
        raise DataSourceError(
            f"Binance fetch failed: {message}",
            details={"symbol": symbol, "type": cls_name},
        ) from e

    return _normalize(klines)
