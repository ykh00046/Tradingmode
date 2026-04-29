"""GET /api/indicators — fetch OHLCV + computed technical indicators."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api import converters, schemas
from core import data_loader, indicators as core_indicators
from core.types.schemas import FetchRequest, Interval, Market

router = APIRouter()


@router.get("/indicators", response_model=schemas.IndicatorsResponse)
def get_indicators(
    market: schemas.MarketLiteral = Query(...),
    symbol: str = Query(..., min_length=1, max_length=20),
    interval: schemas.IntervalLiteral = Query("1d"),
    start: int = Query(...),
    end: int = Query(...),
) -> schemas.IndicatorsResponse:
    req = FetchRequest(
        market=Market(market),
        symbol=symbol,
        interval=Interval(interval),
        start=converters.ms_to_ts(start),
        end=converters.ms_to_ts(end),
    )
    df = data_loader.fetch(req)
    df = core_indicators.compute(df)
    return schemas.IndicatorsResponse(
        market=market,
        symbol=symbol,
        interval=interval,
        candles=converters.df_to_candles(df),
        indicators=converters.df_indicator_columns(df),
        cached=True,
    )
