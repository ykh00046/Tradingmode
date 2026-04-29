"""POST /api/portfolio — bulk portfolio analysis."""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter

from api import converters, schemas
from core import portfolio as core_portfolio
from core.types.schemas import Holding, Market, Portfolio

router = APIRouter()


@router.post("/portfolio", response_model=schemas.PortfolioAnalysisResponse)
def post_portfolio(req: schemas.PortfolioRequest) -> schemas.PortfolioAnalysisResponse:
    holdings = [
        Holding(
            market=Market(h.market),
            symbol=h.symbol,
            quantity=h.quantity,
            avg_price=h.avg_price,
            currency=h.currency,
        )
        for h in req.holdings
    ]
    portfolio = Portfolio(holdings=holdings, base_currency=req.base_currency)

    as_of = converters.ms_to_ts(req.as_of) if req.as_of else None
    analysis = core_portfolio.analyze(portfolio, as_of=as_of)
    return converters.portfolio_analysis_to_response(analysis)
