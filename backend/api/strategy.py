"""Strategy Coach REST endpoints.

- POST /api/strategy/backtest   → 70/30 split backtest using the user DSL
- GET  /api/strategy/builtins   → catalogue for the editor's autocomplete
- GET  /api/strategy/iterations → past attempts (newest first)
"""

from __future__ import annotations

import json
from dataclasses import asdict
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, Query

from api import converters, schemas
from core import data_loader, iteration_log, strategy_engine
from core.types.errors import CacheError
from core.types.schemas import (
    FetchRequest,
    Interval,
    IterationEntry,
    Market,
    OptimizationGoal,
    StrategyDef,
    TradingCosts,
)
from lib.logger import get_logger

router = APIRouter()
log = get_logger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _next_attempt_no(symbol: str, interval: str) -> int:
    try:
        existing = iteration_log.read(symbol, interval, limit=1)
    except CacheError:
        return 1
    if not existing:
        return 1
    return existing[0].attempt_no + 1


def _to_strategy_def(model: schemas.StrategyDefModel) -> StrategyDef:
    costs = TradingCosts(
        commission_bps=model.costs.commission_bps,
        slippage_bps=model.costs.slippage_bps,
        kr_sell_tax_bps=model.costs.kr_sell_tax_bps,
        apply_kr_tax=model.costs.apply_kr_tax,
    )
    return StrategyDef(
        name=model.name,
        buy_when=model.buy_when,
        sell_when=model.sell_when,
        holding_max_bars=model.holding_max_bars,
        costs=costs,
        optimization_goal=OptimizationGoal(model.optimization_goal),
    )


def _persist_iteration(
    market: str,
    symbol: str,
    interval: str,
    strategy_model: schemas.StrategyDefModel,
    result: "strategy_engine.BacktestSplitResult",
) -> tuple[str, int]:
    """Append a row to the parquet log. Failures are logged but never raise —
    a failed log write must not break the backtest response."""
    iteration_id = uuid4().hex
    attempt_no = _next_attempt_no(symbol, interval)

    entry = IterationEntry(
        iteration_id=iteration_id,
        symbol=symbol,
        interval=interval,
        attempt_no=attempt_no,
        strategy_def_json=strategy_model.model_dump_json(),
        is_total_return=result.is_result.total_return,
        oos_total_return=(
            result.oos_result.total_return if result.oos_result else None
        ),
        is_sharpe=result.is_result.sharpe_ratio,
        oos_sharpe=(
            result.oos_result.sharpe_ratio if result.oos_result else None
        ),
        is_mdd=result.is_result.max_drawdown,
        oos_mdd=result.oos_result.max_drawdown if result.oos_result else None,
        is_win_rate=result.is_result.win_rate,
        is_oos_gap_pct=result.is_oos_gap_pct,
        overfit_warning=result.overfit_warning,
        optimization_goal=strategy_model.optimization_goal,
        coach_diagnosis=None,
        applied_recommendation=None,
        timestamp=pd.Timestamp.now(tz="UTC"),
    )
    try:
        iteration_log.append(entry)
    except CacheError as e:
        log.warning("iteration_log.append failed: %s", e)
    return iteration_id, attempt_no


# =============================================================================
# Routes
# =============================================================================


@router.post("/strategy/backtest", response_model=schemas.BacktestSplitResponse)
def post_strategy_backtest(req: schemas.StrategyBacktestRequest) -> schemas.BacktestSplitResponse:
    """Validate user expressions, fetch OHLCV, compute indicators, then
    run a 70/30 split backtest. Optionally appends to the iteration log."""
    fetch_req = FetchRequest(
        market=Market(req.market),
        symbol=req.symbol,
        interval=Interval(req.interval),
        start=converters.ms_to_ts(req.start),
        end=converters.ms_to_ts(req.end),
    )
    df, _ = data_loader.fetch(fetch_req)
    from core import indicators as core_indicators                            # lazy

    df = core_indicators.compute(df)

    strategy_def = _to_strategy_def(req.strategy)
    result = strategy_engine.run_split(
        df,
        strategy_def,
        market=Market(req.market),
        cash=req.cash,
        ratio=req.split_ratio,
    )

    iteration_id: str | None = None
    attempt_no: int | None = None
    if req.persist:
        iteration_id, attempt_no = _persist_iteration(
            req.market, req.symbol, req.interval, req.strategy, result,
        )
    return converters.split_to_response(result, iteration_id, attempt_no)


@router.get("/strategy/builtins", response_model=schemas.StrategyBuiltinsResponse)
def get_strategy_builtins() -> schemas.StrategyBuiltinsResponse:
    """Return everything an editor needs for autocomplete + an AI prompt
    needs to know what's already implemented."""
    return schemas.StrategyBuiltinsResponse(
        indicators=[
            converters.builtin_to_response(b) for b in strategy_engine.BUILTIN_INDICATORS
        ],
        operators=list(strategy_engine.SUPPORTED_OPERATORS),
        helpers=list(strategy_engine.SUPPORTED_HELPERS),
    )


@router.get(
    "/strategy/iterations",
    response_model=list[schemas.IterationEntryModel],
)
def get_strategy_iterations(
    symbol: str = Query(..., min_length=1, max_length=20),
    interval: schemas.IntervalLiteral = Query("1d"),
    limit: int = Query(50, ge=1, le=500),
) -> list[schemas.IterationEntryModel]:
    """Return up to ``limit`` most-recent attempts for ``(symbol, interval)``."""
    entries = iteration_log.read(symbol, interval, limit=limit)
    return [converters.iteration_to_response(e) for e in entries]
