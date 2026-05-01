"""Unit tests for API converters."""

from __future__ import annotations

import pandas as pd

from api import converters
from core.types.schemas import (
    Holding,
    HoldingAnalysis,
    Market,
    Portfolio,
    PortfolioAnalysis,
    SkippedHolding,
    TrendState,
)


def test_portfolio_analysis_response_includes_partial_metadata() -> None:
    holding = Holding(
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        quantity=0.5,
        avg_price=60000,
        currency="USDT",
    )
    analysis = PortfolioAnalysis(
        portfolio=Portfolio(holdings=[holding], base_currency="KRW"),
        holdings_analysis=[
            HoldingAnalysis(
                holding=holding,
                current_price_local=66000,
                current_price=91080000,
                market_value=45540000,
                cost_basis=41400000,
                pnl=4140000,
                pnl_pct=10.0,
                weight=1.0,
                fx_rate=1380.0,
                trend=TrendState.UPTREND,
                latest_signals=[],
            )
        ],
        total_market_value=45540000,
        total_cost_basis=41400000,
        total_pnl=4140000,
        total_pnl_pct=10.0,
        trend_summary={
            TrendState.UPTREND: 1,
            TrendState.DOWNTREND: 0,
            TrendState.SIDEWAYS: 0,
        },
        base_currency="KRW",
        fx_rates={},
        as_of=pd.Timestamp("2026-04-30", tz="UTC"),
        skipped_holdings=[
            SkippedHolding(
                market=Market.KR_STOCK,
                symbol="005930",
                reason="upstream timeout",
            )
        ],
    )

    response = converters.portfolio_analysis_to_response(analysis)

    assert response.partial is True
    assert response.model_dump()["skipped_holdings"] == [
        {
            "market": "kr_stock",
            "symbol": "005930",
            "reason": "upstream timeout",
        }
    ]
