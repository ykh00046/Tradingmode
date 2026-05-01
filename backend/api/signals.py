"""GET /api/signals — detect trading signals."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api import converters, schemas
from core import data_loader, signals as core_signals
from core.types.schemas import FetchRequest, Interval, Market

router = APIRouter()


@router.get("/signals", response_model=schemas.SignalsResponse)
def get_signals(
    market: schemas.MarketLiteral = Query(...),
    symbol: str = Query(..., min_length=1, max_length=20),
    interval: schemas.IntervalLiteral = Query("1d"),
    start: int = Query(...),
    end: int = Query(...),
) -> schemas.SignalsResponse:
    req = FetchRequest(
        market=Market(market),
        symbol=symbol,
        interval=Interval(interval),
        start=converters.ms_to_ts(start),
        end=converters.ms_to_ts(end),
    )
    df, _ = data_loader.fetch(req)
    from core import indicators as core_indicators

    df = core_indicators.compute(df)
    detected = core_signals.detect_all(df)
    return schemas.SignalsResponse(
        market=market,
        symbol=symbol,
        signals=converters.signals_to_out(detected),
    )
