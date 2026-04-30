"""Unified entry point for OHLCV data — caches, then routes to the right adapter."""

from __future__ import annotations

import pandas as pd

from core.adapters import binance_adapter, krx_adapter
from core.types.errors import DataSourceError
from core.types.schemas import FetchRequest, Market
from lib import cache
from lib.logger import get_logger

log = get_logger(__name__)


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
    start_str = req.start.strftime("%Y-%m-%d")
    end_str = req.end.strftime("%Y-%m-%d")
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
