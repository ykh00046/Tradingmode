"""Unit tests for ``core.portfolio``."""

from __future__ import annotations

import pandas as pd
import pytest

from core import portfolio as portfolio_module
from core.types.errors import PortfolioError
from core.types.schemas import (
    Holding,
    HoldingAnalysis,
    Market,
    Portfolio,
    Signal,
    SignalAction,
    SignalKind,
    TrendState,
)


# =============================================================================
# CSV input
# =============================================================================


def test_load_holdings_from_csv_parses_valid_file(tmp_path) -> None:
    csv = tmp_path / "h.csv"
    csv.write_text(
        "market,symbol,quantity,avg_price,currency\n"
        "crypto,BTCUSDT,0.05,65000,USDT\n"
        "kr_stock,005930,100,72000,KRW\n",
        encoding="utf-8",
    )
    p = portfolio_module.load_holdings_from_csv(csv)
    assert len(p.holdings) == 2
    assert p.holdings[0].symbol == "BTCUSDT"
    assert p.holdings[0].quantity == 0.05
    assert p.holdings[1].currency == "KRW"


def test_load_holdings_missing_columns_raises(tmp_path) -> None:
    csv = tmp_path / "h.csv"
    csv.write_text("market,symbol,quantity\ncrypto,BTC,1\n", encoding="utf-8")
    with pytest.raises(PortfolioError, match="missing required columns"):
        portfolio_module.load_holdings_from_csv(csv)


def test_load_holdings_negative_quantity_raises(tmp_path) -> None:
    csv = tmp_path / "h.csv"
    csv.write_text(
        "market,symbol,quantity,avg_price,currency\n"
        "crypto,BTCUSDT,-1,65000,USDT\n",
        encoding="utf-8",
    )
    with pytest.raises(PortfolioError, match="row 2"):
        portfolio_module.load_holdings_from_csv(csv)


def test_load_holdings_empty_file_raises(tmp_path) -> None:
    csv = tmp_path / "h.csv"
    csv.write_text("market,symbol,quantity,avg_price,currency\n", encoding="utf-8")
    with pytest.raises(PortfolioError, match="no holdings"):
        portfolio_module.load_holdings_from_csv(csv)


def test_load_holdings_unsupported_currency_raises(tmp_path) -> None:
    csv = tmp_path / "h.csv"
    csv.write_text(
        "market,symbol,quantity,avg_price,currency\n"
        "crypto,BTCUSDT,1,65000,EUR\n",
        encoding="utf-8",
    )
    with pytest.raises(PortfolioError, match="unsupported currency"):
        portfolio_module.load_holdings_from_csv(csv)


def test_load_holdings_csv_not_found(tmp_path) -> None:
    with pytest.raises(PortfolioError, match="CSV not found"):
        portfolio_module.load_holdings_from_csv(tmp_path / "missing.csv")


# =============================================================================
# Aggregation helpers
# =============================================================================


def _ha(symbol: str, *, value: float, cost: float, trend: TrendState) -> HoldingAnalysis:
    h = Holding(market=Market.KR_STOCK, symbol=symbol, quantity=1, avg_price=cost, currency="KRW")
    return HoldingAnalysis(
        holding=h,
        current_price_local=value,
        current_price=value,
        market_value=value,
        cost_basis=cost,
        pnl=value - cost,
        pnl_pct=(value - cost) / cost * 100 if cost else 0.0,
        weight=0.0,
        fx_rate=1.0,
        trend=trend,
        latest_signals=[],
    )


def test_aggregate_trend_counts_all_states() -> None:
    analyses = [
        _ha("A", value=100, cost=80, trend=TrendState.UPTREND),
        _ha("B", value=70, cost=80, trend=TrendState.UPTREND),
        _ha("C", value=90, cost=100, trend=TrendState.DOWNTREND),
    ]
    summary = portfolio_module.aggregate_trend(analyses)
    assert summary[TrendState.UPTREND] == 2
    assert summary[TrendState.DOWNTREND] == 1
    assert summary[TrendState.SIDEWAYS] == 0


# =============================================================================
# analyze() — full pipeline (heavily mocked)
# =============================================================================


def test_analyze_aggregates_correctly(mocker) -> None:
    """Mock everything below `analyze` and verify totals + weights."""
    portfolio = Portfolio(
        holdings=[
            Holding(market=Market.KR_STOCK, symbol="A", quantity=10, avg_price=50, currency="KRW"),
            Holding(market=Market.KR_STOCK, symbol="B", quantity=5, avg_price=200, currency="KRW"),
        ],
        base_currency="KRW",
    )

    def _fake_analyze_holding(holding, fx_rates, base, lookback, as_of):
        # A at 100 (was 50), B at 100 (was 200)
        prices = {"A": 100.0, "B": 100.0}
        local = prices[holding.symbol]
        market_value = holding.quantity * local
        cost_basis = holding.quantity * holding.avg_price
        return HoldingAnalysis(
            holding=holding,
            current_price_local=local,
            current_price=local,
            market_value=market_value,
            cost_basis=cost_basis,
            pnl=market_value - cost_basis,
            pnl_pct=(market_value - cost_basis) / cost_basis * 100,
            weight=0.0,
            fx_rate=1.0,
            trend=TrendState.UPTREND,
            latest_signals=[],
        )

    mocker.patch("core.portfolio._analyze_holding", side_effect=_fake_analyze_holding)
    mocker.patch("core.portfolio._resolve_fx_rates", return_value={})

    result = portfolio_module.analyze(portfolio, as_of=pd.Timestamp("2026-04-30"))

    # A: 10 × 100 = 1000, cost 500. B: 5 × 100 = 500, cost 1000. Total: 1500 / 1500 → 0% PnL
    assert result.total_market_value == pytest.approx(1500.0)
    assert result.total_cost_basis == pytest.approx(1500.0)
    assert result.total_pnl == pytest.approx(0.0)
    assert result.total_pnl_pct == pytest.approx(0.0)

    # Weights should sum to 1.0 (within float tolerance)
    weights = sum(a.weight for a in result.holdings_analysis)
    assert weights == pytest.approx(1.0)

    assert result.trend_summary[TrendState.UPTREND] == 2


def test_analyze_skips_failing_holding(mocker, caplog) -> None:
    """One bad ticker should not break the whole portfolio analysis."""
    portfolio = Portfolio(
        holdings=[
            Holding(market=Market.KR_STOCK, symbol="GOOD", quantity=1, avg_price=100, currency="KRW"),
            Holding(market=Market.KR_STOCK, symbol="BAD", quantity=1, avg_price=100, currency="KRW"),
        ],
        base_currency="KRW",
    )

    def _fake_analyze_holding(holding, *args, **kwargs):
        if holding.symbol == "BAD":
            raise RuntimeError("simulated failure")
        return HoldingAnalysis(
            holding=holding,
            current_price_local=120.0,
            current_price=120.0,
            market_value=120.0,
            cost_basis=100.0,
            pnl=20.0,
            pnl_pct=20.0,
            weight=0.0,
            fx_rate=1.0,
            trend=TrendState.UPTREND,
            latest_signals=[],
        )

    mocker.patch("core.portfolio._analyze_holding", side_effect=_fake_analyze_holding)
    mocker.patch("core.portfolio._resolve_fx_rates", return_value={})

    result = portfolio_module.analyze(portfolio)

    # Only the GOOD holding made it through
    assert len(result.holdings_analysis) == 1
    assert result.holdings_analysis[0].holding.symbol == "GOOD"
