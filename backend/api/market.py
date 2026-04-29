"""GET /api/market/snapshot — TopBar tape (KOSPI/KOSDAQ/USD-KRW/BTC/DXY/VIX)."""

from __future__ import annotations

from fastapi import APIRouter

from api import converters, schemas
from core import market_snapshot

router = APIRouter()


@router.get("/market/snapshot", response_model=schemas.MarketSnapshotResponse)
def get_market_snapshot() -> schemas.MarketSnapshotResponse:
    """Return market overview. Cached in-memory by ``core.market_snapshot`` for 30s."""
    snap = market_snapshot.fetch_snapshot()
    return converters.snapshot_to_response(snap)
