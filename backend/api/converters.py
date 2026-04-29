"""Helpers for converting domain dataclasses (``core.types.schemas``) into
the JSON-friendly Pydantic models in ``api.schemas``.

Centralised so the field-mapping policy (timestamps in unix ms, NaN → None,
DataFrame → list[dict], etc.) lives in exactly one place.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from api import schemas as api_schemas
from core.types.schemas import (
    AICommentary,
    BacktestResult,
    FxQuote,
    HoldingAnalysis,
    IndexQuote,
    MarketSnapshot,
    PortfolioAnalysis,
    Signal,
    TrendState,
)

# =============================================================================
# Primitives
# =============================================================================


def ts_to_ms(ts: pd.Timestamp) -> int:
    """``pd.Timestamp`` → unix milliseconds (UTC)."""
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.timestamp() * 1000)


def ms_to_ts(ms: int) -> pd.Timestamp:
    return pd.Timestamp(ms, unit="ms", tz="UTC")


def _none_if_nan(x: Any) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


# =============================================================================
# OHLCV / Indicators
# =============================================================================


_OHLCV_KEEP = ("open", "high", "low", "close", "volume")
_INDICATOR_PREFIXES = ("SMA_", "EMA_", "RSI_", "MACD", "BB", "ADX", "DMP_", "DMN_", "STOCH")


def df_to_candles(df: pd.DataFrame) -> list[api_schemas.Candle]:
    """OHLCV ``DataFrame`` → ``list[Candle]``."""
    return [
        api_schemas.Candle(
            t=ts_to_ms(idx),
            o=float(row["open"]),
            h=float(row["high"]),
            l=float(row["low"]),
            c=float(row["close"]),
            v=float(row["volume"]),
        )
        for idx, row in df.iterrows()
    ]


def _split_indicator_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if any(c.startswith(p) for p in _INDICATOR_PREFIXES)]


def df_indicator_columns(df: pd.DataFrame) -> dict[str, list[float | None]]:
    """Return a dict {column_name: list[float|None]} for every indicator column.

    NaN / inf values are converted to ``None`` so the result is JSON-safe.
    """
    out: dict[str, list[float | None]] = {}
    for col in _split_indicator_columns(df):
        values = df[col].astype(float).tolist()
        out[col] = [_none_if_nan(v) for v in values]
    return out


# =============================================================================
# Signals
# =============================================================================


def signal_to_out(signal: Signal) -> api_schemas.SignalOut:
    return api_schemas.SignalOut(
        timestamp=ts_to_ms(signal.timestamp),
        kind=signal.kind.value,
        action=signal.action.value,
        price=signal.price,
        strength=signal.strength,
        detail=signal.detail,
    )


def signals_to_out(signals: list[Signal]) -> list[api_schemas.SignalOut]:
    return [signal_to_out(s) for s in signals]


# =============================================================================
# Trend
# =============================================================================


def trend_to_response(
    trend: TrendState,
    market: str,
    symbol: str,
    df: pd.DataFrame | None,
) -> api_schemas.TrendResponse:
    adx: float | None = None
    ma_alignment: dict[str, float | None] = {}
    if df is not None and len(df) > 0:
        last = df.iloc[-1]
        adx = _none_if_nan(last.get("ADX_14"))
        for period in (20, 60, 120):
            ma_alignment[f"sma_{period}"] = _none_if_nan(last.get(f"SMA_{period}"))
    return api_schemas.TrendResponse(
        market=market,                                                       # type: ignore[arg-type]
        symbol=symbol,
        trend=trend.value,                                                   # type: ignore[arg-type]
        adx=adx,
        ma_alignment=ma_alignment,
    )


# =============================================================================
# AI commentary
# =============================================================================


def commentary_to_response(c: AICommentary) -> api_schemas.AICommentaryResponse:
    return api_schemas.AICommentaryResponse(
        signal_kind=c.signal_kind.value,
        timestamp=ts_to_ms(c.timestamp),
        summary=c.summary,
        detail=c.detail,
        confidence=c.confidence,
        model=c.model,
        generated_at=ts_to_ms(c.generated_at),
        disclaimer=c.disclaimer,
    )


# =============================================================================
# Portfolio
# =============================================================================


def fx_to_response(q: FxQuote) -> api_schemas.FxQuoteResponse:
    return api_schemas.FxQuoteResponse(
        pair=q.pair, rate=q.rate, as_of=ts_to_ms(q.as_of), source=q.source,
    )


def holding_analysis_to_response(ha: HoldingAnalysis) -> api_schemas.HoldingAnalysisResponse:
    return api_schemas.HoldingAnalysisResponse(
        market=ha.holding.market.value,                                      # type: ignore[arg-type]
        symbol=ha.holding.symbol,
        quantity=ha.holding.quantity,
        avg_price=ha.holding.avg_price,
        currency=ha.holding.currency,
        current_price_local=ha.current_price_local,
        current_price=ha.current_price,
        market_value=ha.market_value,
        cost_basis=ha.cost_basis,
        pnl=ha.pnl,
        pnl_pct=ha.pnl_pct,
        weight=ha.weight,
        fx_rate=ha.fx_rate,
        trend=ha.trend.value,
        latest_signals=signals_to_out(ha.latest_signals),
    )


def portfolio_analysis_to_response(
    pa: PortfolioAnalysis,
) -> api_schemas.PortfolioAnalysisResponse:
    return api_schemas.PortfolioAnalysisResponse(
        holdings_analysis=[holding_analysis_to_response(a) for a in pa.holdings_analysis],
        total_market_value=pa.total_market_value,
        total_cost_basis=pa.total_cost_basis,
        total_pnl=pa.total_pnl,
        total_pnl_pct=pa.total_pnl_pct,
        trend_summary={state.value: count for state, count in pa.trend_summary.items()},
        base_currency=pa.base_currency,                                      # type: ignore[arg-type]
        fx_rates={pair: fx_to_response(q) for pair, q in pa.fx_rates.items()},
        as_of=ts_to_ms(pa.as_of),
    )


# =============================================================================
# Backtest
# =============================================================================


def equity_curve_to_points(curve: pd.Series) -> list[api_schemas.EquityPoint]:
    """``equity_curve`` Series → list of {t, equity}."""
    points: list[api_schemas.EquityPoint] = []
    for ts, equity in curve.items():
        # Some backtesting.py versions emit string indices; coerce defensively.
        if isinstance(ts, pd.Timestamp):
            t_ms = ts_to_ms(ts)
        else:
            try:
                t_ms = ts_to_ms(pd.Timestamp(ts))
            except Exception:
                continue
        v = _none_if_nan(equity)
        if v is None:
            continue
        points.append(api_schemas.EquityPoint(t=t_ms, equity=v))
    return points


def trades_to_dicts(trades: pd.DataFrame) -> list[dict]:
    """Convert backtesting.py trades DataFrame to JSON-safe list of dicts."""
    if trades is None or trades.empty:
        return []
    # Pandas may carry numpy types and NaT — sanitise to plain Python.
    df = trades.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].apply(lambda v: ts_to_ms(v) if pd.notna(v) else None)
        elif pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].apply(_none_if_nan)
    return df.to_dict(orient="records")


def backtest_to_response(result: BacktestResult) -> api_schemas.BacktestResultResponse:
    return api_schemas.BacktestResultResponse(
        total_return=result.total_return,
        annual_return=result.annual_return,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        sharpe_ratio=result.sharpe_ratio,
        num_trades=result.num_trades,
        equity_curve=equity_curve_to_points(result.equity_curve),
        trades=trades_to_dicts(result.trades),
    )


# =============================================================================
# Market snapshot
# =============================================================================


def index_quote_to_response(q: IndexQuote) -> api_schemas.IndexQuoteResponse:
    return api_schemas.IndexQuoteResponse(value=q.value, change_pct=q.change_pct)


def snapshot_to_response(s: MarketSnapshot) -> api_schemas.MarketSnapshotResponse:
    return api_schemas.MarketSnapshotResponse(
        kospi=index_quote_to_response(s.kospi),
        kosdaq=index_quote_to_response(s.kosdaq),
        usd_krw=index_quote_to_response(s.usd_krw),
        btc=index_quote_to_response(s.btc),
        dxy=index_quote_to_response(s.dxy),
        vix=index_quote_to_response(s.vix),
        timestamp=ts_to_ms(s.timestamp),
    )


# =============================================================================
# Re-exports useful for tests
# =============================================================================

__all__ = [
    "ts_to_ms",
    "ms_to_ts",
    "df_to_candles",
    "df_indicator_columns",
    "signal_to_out",
    "signals_to_out",
    "trend_to_response",
    "commentary_to_response",
    "fx_to_response",
    "holding_analysis_to_response",
    "portfolio_analysis_to_response",
    "backtest_to_response",
    "snapshot_to_response",
]
