"""POST /api/ai/explain — Groq LLM signal commentary."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from api import converters, schemas
from core import ai_interpreter, data_loader, indicators as core_indicators
from core.types.schemas import FetchRequest, Interval, Market, Signal, SignalAction, SignalKind

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
