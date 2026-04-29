"""GET /api/ohlcv — fetch OHLCV candles."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from api import converters, schemas
from core import data_loader
from core.types.schemas import FetchRequest, Interval, Market

router = APIRouter()


@router.get("/ohlcv", response_model=schemas.OHLCVResponse)
def get_ohlcv(
    market: schemas.MarketLiteral = Query(...),
    symbol: str = Query(..., min_length=1, max_length=20),
    interval: schemas.IntervalLiteral = Query("1d"),
    start: int = Query(..., description="unix ms inclusive"),
    end: int = Query(..., description="unix ms exclusive"),
) -> schemas.OHLCVResponse:
    req = FetchRequest(
        market=Market(market),
        symbol=symbol,
        interval=Interval(interval),
        start=converters.ms_to_ts(start),
        end=converters.ms_to_ts(end),
    )
    df = data_loader.fetch(req)
    return schemas.OHLCVResponse(
        market=market,
        symbol=symbol,
        interval=interval,
        candles=converters.df_to_candles(df),
        cached=True,                                # We always go through the cache layer; "cached" here means served from cache or freshly stored
    )
