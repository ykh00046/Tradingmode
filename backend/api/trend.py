"""GET /api/trend — classify the most-recent trend.

When ``series=true`` the response also carries a per-bar trend timeseries so
the frontend doesn't need to re-implement ``classify_series`` in JavaScript.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from api import converters, schemas
from core import data_loader, trend as core_trend
from core.types.schemas import FetchRequest, Interval, Market

router = APIRouter()


@router.get("/trend", response_model=schemas.TrendResponseExt)
def get_trend(
    market: schemas.MarketLiteral = Query(...),
    symbol: str = Query(..., min_length=1, max_length=20),
    interval: schemas.IntervalLiteral = Query("1d"),
    start: int = Query(...),
    end: int = Query(...),
    series: bool = Query(False, description="Include per-bar trend series"),
) -> schemas.TrendResponseExt:
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
    state = core_trend.classify(df)
    base = converters.trend_to_response(state, market, symbol, df)
    series_points = (
        converters.trend_series_to_points(core_trend.classify_series(df))
        if series
        else None
    )
    return schemas.TrendResponseExt(
        market=base.market,
        symbol=base.symbol,
        trend=base.trend,
        adx=base.adx,
        ma_alignment=base.ma_alignment,
        series=series_points,
    )
