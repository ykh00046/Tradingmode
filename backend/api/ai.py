"""POST /api/ai/explain        — Groq LLM signal commentary.
POST /api/ai/strategy-coach — boost recommendations for a user strategy.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from api import converters, schemas
from core import ai_interpreter, data_loader
from core import strategy_coach as coach_module
from core import strategy_engine
from core.types.schemas import (
    BacktestResult,
    FetchRequest,
    Interval,
    Market,
    OptimizationGoal,
    Signal,
    SignalAction,
    SignalKind,
    StrategyDef,
    TradingCosts,
)

router = APIRouter()


def _resolve_action(kind: SignalKind) -> SignalAction:
    """Map a signal kind to its default direction (used when reconstructing
    a Signal from the API request)."""
    buy = {
        SignalKind.GOLDEN_CROSS,
        SignalKind.RSI_OVERSOLD,
        SignalKind.RSI_BULL_DIV,
        SignalKind.MACD_BULL_CROSS,
    }
    return SignalAction.BUY if kind in buy else SignalAction.SELL


@router.post("/ai/explain", response_model=schemas.AICommentaryResponse)
def post_ai_explain(req: schemas.AIExplainRequest) -> schemas.AICommentaryResponse:
    """Generate (or load cached) commentary for a single signal.

    The frontend already has the OHLCV + indicators it rendered; we re-fetch
    a small window here so the LLM prompt includes the actual indicator values
    at the signal timestamp. This keeps the request payload tiny and avoids
    trusting client-supplied numbers.
    """
    kind = SignalKind(req.signal_kind)
    ts = converters.ms_to_ts(req.timestamp)

    # Pull a window of bars around the signal so the LLM has context. 60 bars
    # is enough for SMA_60 / MACD slow=26 to be valid at the signal point.
    fetch_req = FetchRequest(
        market=Market(req.market),
        symbol=req.symbol,
        interval=Interval(req.interval),
        start=ts - pd.Timedelta(days=120),
        end=ts + pd.Timedelta(days=1),
    )
    df, _ = data_loader.fetch(fetch_req)
    from core import indicators as core_indicators

    df = core_indicators.compute(df)

    signal = Signal(
        timestamp=ts,
        kind=kind,
        action=_resolve_action(kind),
        price=req.price,
        strength=1.0,
        detail={},
    )
    commentary = ai_interpreter.interpret_signal(signal, df, req.symbol)
    return converters.commentary_to_response(commentary)


# =============================================================================
# Strategy coach (v0.5)
# =============================================================================


def _model_to_strategy_def(m: schemas.StrategyDefModel) -> StrategyDef:
    return StrategyDef(
        name=m.name,
        buy_when=m.buy_when,
        sell_when=m.sell_when,
        holding_max_bars=m.holding_max_bars,
        costs=TradingCosts(
            commission_bps=m.costs.commission_bps,
            slippage_bps=m.costs.slippage_bps,
            kr_sell_tax_bps=m.costs.kr_sell_tax_bps,
            apply_kr_tax=m.costs.apply_kr_tax,
        ),
        optimization_goal=OptimizationGoal(m.optimization_goal),
    )


def _summary_to_backtest_result(s: schemas.IsResultSummary) -> BacktestResult:
    """Coach prompt only consumes the 6-scalar summary; we wrap it back into a
    ``BacktestResult`` with empty equity/trades so the existing
    ``recommend()`` signature stays unchanged."""
    return BacktestResult(
        total_return=s.total_return,
        annual_return=s.annual_return,
        max_drawdown=s.max_drawdown,
        win_rate=s.win_rate,
        sharpe_ratio=s.sharpe_ratio,
        num_trades=s.num_trades,
        equity_curve=pd.Series(dtype=float),
        trades=pd.DataFrame(),
    )


@router.post("/ai/strategy-coach", response_model=schemas.CoachResponseModel)
def post_strategy_coach(req: schemas.StrategyCoachRequest) -> schemas.CoachResponseModel:
    """Send IS stats + strategy + builtin catalogue to Groq, return parsed
    diagnosis + recommendations."""
    strategy_def = _model_to_strategy_def(req.strategy)
    is_result = _summary_to_backtest_result(req.is_result)
    response = coach_module.recommend(
        strategy=strategy_def,
        is_result=is_result,
        builtin_indicators=strategy_engine.BUILTIN_INDICATORS,
        history_summary=req.history_summary,
    )
    return converters.coach_to_response(response)
