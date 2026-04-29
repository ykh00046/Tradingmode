"""Market snapshot for the TopBar — KOSPI / KOSDAQ / USD-KRW / BTC / DXY / VIX.

All values are sourced from FinanceDataReader except BTC, which uses Binance
spot. The result is cached in-memory for 30s to match the frontend polling
cadence; a TTL longer than the polling interval avoids burning fetches when
the user has multiple tabs open.
"""

from __future__ import annotations

import time
from typing import Callable

import pandas as pd

from core.adapters import binance_adapter
from core.types.errors import DataSourceError
from core.types.schemas import IndexQuote, Interval, MarketSnapshot
from lib.logger import get_logger

log = get_logger(__name__)


_CACHE_TTL_SEC = 30
_cache: dict[str, tuple[float, MarketSnapshot]] = {}


# =============================================================================
# Per-asset fetchers
# =============================================================================


def _fdr_index_quote(ticker: str, *, fallback: IndexQuote) -> IndexQuote:
    """Fetch the latest two daily bars from FDR and return value + day change %."""
    try:
        import FinanceDataReader as fdr                                      # type: ignore

        # 7 days back gives us at least one trading day's worth even on a Monday.
        end = pd.Timestamp.utcnow()
        start = end - pd.Timedelta(days=7)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if df is None or len(df) < 2:
            return fallback
        df = df.rename(columns=str.lower)
        last = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        change_pct = (last - prev) / prev * 100 if prev else 0.0
        return IndexQuote(value=last, change_pct=change_pct)
    except Exception as e:                                                   # pragma: no cover
        log.warning("fdr fetch %s failed: %s — fallback %s", ticker, e, fallback)
        return fallback


def _btc_quote() -> IndexQuote:
    """Latest BTC/USDT spot via Binance daily candles."""
    fallback = IndexQuote(value=0.0, change_pct=0.0)
    try:
        end = pd.Timestamp.utcnow()
        start = end - pd.Timedelta(days=3)
        df = binance_adapter.download("BTCUSDT", "1d", start, end)
        if df is None or len(df) < 2:
            return fallback
        last = float(df["close"].iloc[-1])
        prev = float(df["close"].iloc[-2])
        change_pct = (last - prev) / prev * 100 if prev else 0.0
        return IndexQuote(value=last, change_pct=change_pct)
    except DataSourceError as e:                                             # pragma: no cover
        log.warning("btc fetch failed: %s", e)
        return fallback


# =============================================================================
# Public API
# =============================================================================


def fetch_snapshot(*, force_refresh: bool = False) -> MarketSnapshot:
    """Fetch (or return cached) market snapshot for the TopBar."""
    now = time.time()
    if not force_refresh:
        cached = _cache.get("snapshot")
        if cached and (now - cached[0]) < _CACHE_TTL_SEC:
            return cached[1]

    log.info("market snapshot fetch (force_refresh=%s)", force_refresh)

    # Each fetcher returns a sensible fallback on failure so a single bad
    # source can never crash the TopBar.
    snapshot = MarketSnapshot(
        kospi=_fdr_index_quote("KS11", fallback=IndexQuote(0.0, 0.0)),
        kosdaq=_fdr_index_quote("KQ11", fallback=IndexQuote(0.0, 0.0)),
        usd_krw=_fdr_index_quote("USD/KRW", fallback=IndexQuote(0.0, 0.0)),
        btc=_btc_quote(),
        dxy=_fdr_index_quote("DX-Y.NYB", fallback=IndexQuote(0.0, 0.0)),
        vix=_fdr_index_quote("VIX", fallback=IndexQuote(0.0, 0.0)),
        timestamp=pd.Timestamp.utcnow(),
    )

    _cache["snapshot"] = (now, snapshot)
    return snapshot
