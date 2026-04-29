"""Tests for POST /api/portfolio."""

from __future__ import annotations

import pandas as pd

from core.types.schemas import (
    HoldingAnalysis,
    Holding,
    Market,
    Portfolio,
    PortfolioAnalysis,
    TrendState,
)


_VALID_BODY = {
    "holdings": [
        {"market": "crypto", "symbol": "BTCUSDT", "quantity": 0.5, "avg_price": 60000, "currency": "USDT"},
        {"market": "kr_stock", "symbol": "005930", "quantity": 100, "avg_price": 70000, "currency": "KRW"},
    ],
    "base_currency": "KRW",
}


def _fake_analysis(portfolio: Portfolio, **_) -> PortfolioAnalysis:
    """Build a deterministic PortfolioAnalysis matching the request body."""
    analyses = []
    total = 0.0
    for h in portfolio.holdings:
        market_value = h.quantity * h.avg_price * 1.1  # +10%
        total += market_value
    for h in portfolio.holdings:
        market_value = h.quantity * h.avg_price * 1.1
        analyses.append(
            HoldingAnalysis(
                holding=h,
                current_price_local=h.avg_price * 1.1,
                current_price=h.avg_price * 1.1,
                market_value=market_value,
                cost_basis=h.quantity * h.avg_price,
                pnl=market_value - h.quantity * h.avg_price,
                pnl_pct=10.0,
                weight=market_value / total,
                fx_rate=1.0,
                trend=TrendState.UPTREND,
                latest_signals=[],
            )
        )
    cost = sum(a.cost_basis for a in analyses)
    return PortfolioAnalysis(
        portfolio=portfolio,
        holdings_analysis=analyses,
        total_market_value=total,
        total_cost_basis=cost,
        total_pnl=total - cost,
        total_pnl_pct=(total - cost) / cost * 100,
        trend_summary={TrendState.UPTREND: len(analyses), TrendState.DOWNTREND: 0, TrendState.SIDEWAYS: 0},
        base_currency="KRW",
        fx_rates={},
        as_of=pd.Timestamp("2026-04-30", tz="UTC"),
    )


def test_portfolio_returns_analysis(client, mocker) -> None:
    mocker.patch("api.portfolio.core_portfolio.analyze", side_effect=_fake_analysis)
    res = client.post("/api/portfolio", json=_VALID_BODY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["holdings_analysis"]) == 2
    weights = sum(h["weight"] for h in body["holdings_analysis"])
    assert abs(weights - 1.0) < 1e-9
    assert body["total_pnl_pct"] > 0
    assert body["trend_summary"]["uptrend"] == 2


def test_portfolio_rejects_empty_holdings(client) -> None:
    res = client.post("/api/portfolio", json={"holdings": []})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


def test_portfolio_rejects_negative_quantity(client) -> None:
    bad = {
        "holdings": [
            {"market": "crypto", "symbol": "BTCUSDT", "quantity": -1, "avg_price": 60000, "currency": "USDT"}
        ]
    }
    res = client.post("/api/portfolio", json=bad)
    assert res.status_code == 400
