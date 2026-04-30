"""POST /api/backtest — run a strategy on historical data."""

from __future__ import annotations

from fastapi import APIRouter

from api import converters, schemas
from core import backtest as core_backtest, data_loader
from core.types.schemas import FetchRequest, Interval, Market

router = APIRouter()


@router.post("/backtest", response_model=schemas.BacktestResultResponse)
def post_backtest(req: schemas.BacktestRequest) -> schemas.BacktestResultResponse:
    fetch_req = FetchRequest(
        market=Market(req.market),
        symbol=req.symbol,
        interval=Interval(req.interval),
        start=converters.ms_to_ts(req.start),
        end=converters.ms_to_ts(req.end),
    )
    df, _ = data_loader.fetch(fetch_req)
    result = core_backtest.run(
        df,
        strategy=req.strategy,
        cash=req.cash,
        commission=req.commission,
    )
    return converters.backtest_to_response(result)
