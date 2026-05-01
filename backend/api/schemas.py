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


class SkippedHoldingResponse(BaseModel):
    market: MarketLiteral
    symbol: str
    reason: str


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
    partial: bool = False
    skipped_holdings: list[SkippedHoldingResponse] = Field(default_factory=list)


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


# =============================================================================
# Strategy Coach (v0.5)
# =============================================================================


GoalLiteral = Literal["return", "sharpe", "mdd", "win_rate"]
RoleLiteral = Literal["filter", "exit_rule", "entry_filter", "sizing"]


class TradingCostsModel(BaseModel):
    """Per-trade frictional costs in basis points (1 bp = 0.01%)."""
    commission_bps: float = Field(default=5.0, ge=0, le=100)
    slippage_bps: float = Field(default=2.0, ge=0, le=100)
    kr_sell_tax_bps: float = Field(default=18.0, ge=0, le=50)
    apply_kr_tax: bool = True


class StrategyDefModel(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    buy_when: str = Field(min_length=1, max_length=500)
    sell_when: str = Field(min_length=1, max_length=500)
    holding_max_bars: int | None = Field(default=None, gt=0)
    costs: TradingCostsModel = Field(default_factory=TradingCostsModel)
    optimization_goal: GoalLiteral = "sharpe"


class StrategyBacktestRequest(BaseModel):
    market: MarketLiteral
    symbol: str
    interval: IntervalLiteral = "1d"
    start: int                                   # unix ms
    end: int
    split_ratio: float = Field(default=0.7, gt=0.5, lt=0.95)
    cash: float = Field(default=10_000_000, gt=0)
    strategy: StrategyDefModel
    persist: bool = True                         # whether to append to iteration_log


class BacktestSplitResponse(BaseModel):
    is_result: BacktestResultResponse
    oos_result: BacktestResultResponse | None = None
    is_period_start: int                          # unix ms
    is_period_end: int
    oos_period_start: int | None = None
    oos_period_end: int | None = None
    is_oos_gap_pct: float | None = None
    overfit_warning: bool = False
    costs_applied: TradingCostsModel
    warnings: list[str] = Field(default_factory=list)
    iteration_id: str | None = None              # populated when persist=True
    attempt_no: int | None = None


class IsResultSummary(BaseModel):
    """Compact 6-scalar IS summary used by the coach prompt."""
    total_return: float
    annual_return: float
    max_drawdown: float
    win_rate: float
    sharpe_ratio: float
    num_trades: int


class StrategyCoachRequest(BaseModel):
    strategy: StrategyDefModel
    is_result: IsResultSummary
    history_summary: list[dict] | None = None


class CoachRecommendationModel(BaseModel):
    indicator: str
    params: dict = Field(default_factory=dict)
    role: RoleLiteral
    reason: str
    expected_synergy: str
    available: bool
    sample_rule: str | None = None


class CoachResponseModel(BaseModel):
    diagnosis: str
    recommendations: list[CoachRecommendationModel]
    warnings: list[str] = Field(default_factory=list)
    model: str
    generated_at: int
    disclaimer: str


class BuiltinIndicatorModel(BaseModel):
    name: str
    columns: list[str]
    params: dict = Field(default_factory=dict)
    description: str
    category: Literal["momentum", "trend", "volatility", "volume"]


class StrategyBuiltinsResponse(BaseModel):
    indicators: list[BuiltinIndicatorModel]
    operators: list[str]
    helpers: list[str]


class IterationEntryModel(BaseModel):
    iteration_id: str
    symbol: str
    interval: str
    attempt_no: int
    strategy_def_json: str
    is_total_return: float
    oos_total_return: float | None = None
    is_sharpe: float
    oos_sharpe: float | None = None
    is_mdd: float
    oos_mdd: float | None = None
    is_win_rate: float
    is_oos_gap_pct: float | None = None
    overfit_warning: bool
    optimization_goal: str
    coach_diagnosis: str | None = None
    applied_recommendation: str | None = None
    timestamp: int                               # unix ms


# === Trend series extension =================================================


class TrendSeriesPoint(BaseModel):
    t: int                                       # unix ms
    state: Literal["uptrend", "downtrend", "sideways"]


class TrendResponseExt(TrendResponse):
    series: list[TrendSeriesPoint] | None = None
