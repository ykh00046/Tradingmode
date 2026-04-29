"""Pydantic request / response models for the REST API.

These mirror ``core.types.schemas`` dataclasses but use JSON-friendly types
(unix-ms ints instead of ``pd.Timestamp``, ``list[dict]`` instead of
``pd.DataFrame``, etc). Conversion lives in ``api.converters``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Errors
# =============================================================================


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


# =============================================================================
# OHLCV
# =============================================================================


MarketLiteral = Literal["crypto", "kr_stock"]
IntervalLiteral = Literal["1m", "5m", "15m", "1h", "4h", "1d"]


class Candle(BaseModel):
    t: int                  # unix ms
    o: float
    h: float
    l: float                # noqa: E741 — convention in market-data libs
    c: float
    v: float


class OHLCVResponse(BaseModel):
    market: MarketLiteral
    symbol: str
    interval: IntervalLiteral
    candles: list[Candle]
    cached: bool = False


# =============================================================================
# Indicators
# =============================================================================


class IndicatorsResponse(BaseModel):
    market: MarketLiteral
    symbol: str
    interval: IntervalLiteral
    candles: list[Candle]
    indicators: dict[str, list[float | None]]
    cached: bool = False


# =============================================================================
# Signals
# =============================================================================


class SignalOut(BaseModel):
    timestamp: int          # unix ms
    kind: str
    action: str
    price: float
    strength: float
    detail: dict


class SignalsResponse(BaseModel):
    market: MarketLiteral
    symbol: str
    signals: list[SignalOut]


# =============================================================================
# Trend
# =============================================================================


class TrendResponse(BaseModel):
    market: MarketLiteral
    symbol: str
    trend: Literal["uptrend", "downtrend", "sideways"]
    adx: float | None = None
    ma_alignment: dict[str, float | None] = Field(default_factory=dict)


# =============================================================================
# AI explain
# =============================================================================


class IndicatorsAtSignal(BaseModel):
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    sma_short: float | None = None
    sma_long: float | None = None
    adx: float | None = None
    bb_upper: float | None = None
    bb_lower: float | None = None


class AIExplainRequest(BaseModel):
    market: MarketLiteral
    symbol: str
    interval: IntervalLiteral = "1d"
    signal_kind: str
    timestamp: int                                  # unix ms
    price: float
    indicators_at_signal: IndicatorsAtSignal | None = None


class AICommentaryResponse(BaseModel):
    signal_kind: str
    timestamp: int
    summary: str
    detail: str
    confidence: Literal["low", "medium", "high"]
    model: str
    generated_at: int
    disclaimer: str


# =============================================================================
# Portfolio
# =============================================================================


class HoldingInput(BaseModel):
    market: MarketLiteral
    symbol: str
    quantity: float = Field(gt=0)
    avg_price: float = Field(gt=0)
    currency: Literal["KRW", "USD", "USDT"]


class PortfolioRequest(BaseModel):
    holdings: list[HoldingInput] = Field(min_length=1)
    base_currency: Literal["KRW", "USD"] = "KRW"
    as_of: int | None = None        # unix ms; ``None`` → latest


class FxQuoteResponse(BaseModel):
    pair: str
    rate: float
    as_of: int                       # unix ms
    source: str


class HoldingAnalysisResponse(BaseModel):
    market: MarketLiteral
    symbol: str
    quantity: float
    avg_price: float
    currency: str
    current_price_local: float
    current_price: float
    market_value: float
    cost_basis: float
    pnl: float
    pnl_pct: float
    weight: float
    fx_rate: float
    trend: str
    latest_signals: list[SignalOut]


class PortfolioAnalysisResponse(BaseModel):
    holdings_analysis: list[HoldingAnalysisResponse]
    total_market_value: float
    total_cost_basis: float
    total_pnl: float
    total_pnl_pct: float
    trend_summary: dict[str, int]
    base_currency: Literal["KRW", "USD"]
    fx_rates: dict[str, FxQuoteResponse]
    as_of: int


# =============================================================================
# Backtest
# =============================================================================


class BacktestRequest(BaseModel):
    market: MarketLiteral
    symbol: str
    interval: IntervalLiteral = "1d"
    start: int                       # unix ms
    end: int                         # unix ms
    strategy: Literal["ma_cross"] = "ma_cross"
    cash: float = Field(default=10_000_000, gt=0)
    commission: float = Field(default=0.0005, ge=0, lt=1)


class EquityPoint(BaseModel):
    t: int
    equity: float


class BacktestResultResponse(BaseModel):
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    sharpe_ratio: float
    num_trades: int
    equity_curve: list[EquityPoint]
    # Trade columns vary by backtesting.py version — keep flexible.
    trades: list[dict]


# =============================================================================
# Market snapshot
# =============================================================================


class IndexQuoteResponse(BaseModel):
    value: float
    change_pct: float


class MarketSnapshotResponse(BaseModel):
    kospi: IndexQuoteResponse
    kosdaq: IndexQuoteResponse
    usd_krw: IndexQuoteResponse
    btc: IndexQuoteResponse
    dxy: IndexQuoteResponse
    vix: IndexQuoteResponse
    timestamp: int


# =============================================================================
# Health
# =============================================================================


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
