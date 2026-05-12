"""Unified entry point for OHLCV data — caches, then routes to the right adapter."""

from __future__ import annotations

import pandas as pd

from core.adapters import binance_adapter, krx_adapter
from core.types.errors import DataSourceError, InvalidSymbolError
from core.types.schemas import FetchRequest, Interval, Market
from lib import cache
from lib.logger import get_logger

log = get_logger(__name__)

# Intervals KRX cannot serve (FDR/pykrx are daily-only; weekly/monthly are
# resampled from daily by krx_adapter, intraday is unsupported entirely).
_KRX_INTRADAY_INTERVALS = frozenset({Interval.M1, Interval.M5, Interval.M15, Interval.H1, Interval.H4})

# Intervals where the user is expected to specify a sub-day window — the cache
# key must include time-of-day, not just date, to avoid intraday windows
# differing only by hour colliding on disk.
_SUBDAY_INTERVALS = frozenset({Interval.M1, Interval.M5, Interval.M15, Interval.H1, Interval.H4})


def _validate_request(req: FetchRequest) -> None:
    """Reject combinations the adapter cannot serve, with a 400-mappable error.

    The adapter would otherwise raise DataSourceError → 502, which mis-attributes
    the failure to the upstream provider rather than to the request itself.
    """
    if req.market == Market.KR_STOCK and req.interval in _KRX_INTRADAY_INTERVALS:
        raise InvalidSymbolError(
            f"{req.interval.value} interval not supported for KR stocks "
            f"(only 1d/1w/1M)",
            details={"market": req.market.value, "interval": req.interval.value},
        )


def _route(req: FetchRequest) -> pd.DataFrame:
    """Dispatch the request to the appropriate market adapter."""
    if req.market == Market.CRYPTO:
        return binance_adapter.download(req.symbol, req.interval.value, req.start, req.end)
    if req.market == Market.KR_STOCK:
        return krx_adapter.download(req.symbol, req.interval.value, req.start, req.end)
    raise DataSourceError(f"unknown market: {req.market}")


def fetch(req: FetchRequest) -> tuple[pd.DataFrame, bool]:
    """Return ``(df, cache_hit)`` for the request, hitting the cache first.

    ``cache_hit`` is ``True`` when the data was served from a parquet file
    without calling the upstream adapter.

    Raises
    ------
    InvalidSymbolError, InsufficientDataError, DataSourceError
        Propagated from the adapter layer.
    """
    _validate_request(req)
    # Sub-day intervals need hour granularity in the cache key; otherwise two
    # 15m windows on the same day collapse onto the same parquet file.
    if req.interval in _SUBDAY_INTERVALS:
        fmt = "%Y-%m-%dT%H%M"
    else:
        fmt = "%Y-%m-%d"
    start_str = req.start.strftime(fmt)
    end_str = req.end.strftime(fmt)
    path = cache.ohlcv_cache_path(
        market=req.market.value,
        symbol=req.symbol,
        interval=req.interval.value,
        start=start_str,
        end=end_str,
    )

    cached = cache.load_ohlcv(path)
    if cached is not None:
        log.info(
            "cache hit: %s/%s/%s (%d rows)",
            req.market.value,
            req.symbol,
            req.interval.value,
            len(cached),
        )
        return cached, True

    log.info("cache miss: %s/%s/%s — fetching", req.market.value, req.symbol, req.interval.value)
    df = _route(req)
    cache.save_ohlcv(path, df)
    return df, False
