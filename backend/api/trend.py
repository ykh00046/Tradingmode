"""GET /api/trend — classify the most-recent trend."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api import converters, schemas
from core import data_loader, indicators as core_indicators, trend as core_trend
from core.types.schemas import FetchRequest, Interval, Market

router = APIRouter()


@router.get("/trend", response_model=schemas.TrendResponse)
def get_trend(
    market: schemas.MarketLiteral = Query(...),
    symbol: str = Query(..., min_length=1, max_length=20),
    interval: schemas.IntervalLiteral = Query("1d"),
    start: int = Query(...),
    end: int = Query(...),
) -> schemas.TrendResponse:
    req = FetchRequest(
        market=Market(market),
        symbol=symbol,
        interval=Interval(interval),
        start=converters.ms_to_ts(start),
        end=converters.ms_to_ts(end),
    )
    df = data_loader.fetch(req)
    df = core_indicators.compute(df)
    state = core_trend.classify(df)
    return converters.trend_to_response(state, market, symbol, df)
