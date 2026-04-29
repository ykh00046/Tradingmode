"""FastAPI application entry-point.

Run from the ``backend/`` directory:

    uvicorn main:app --reload --port 8000

OpenAPI docs are auto-served at ``/docs``.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env before any module that reads env vars.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from api import ai, backtest, indicators, market, ohlcv, portfolio, signals, trend
from api.schemas import HealthResponse
from core.types.errors import (
    AIServiceError,
    CacheError,
    DataSourceError,
    InsufficientDataError,
    InvalidSymbolError,
    PortfolioError,
    TradingToolError,
)
from lib.logger import get_logger

VERSION = "0.4.1"

log = get_logger(__name__)


# =============================================================================
# App + middleware
# =============================================================================


app = FastAPI(
    title="trading-analysis-tool",
    version=VERSION,
    description=(
        "REST API for the Tradingmode analysis tool. Provides OHLCV data, "
        "technical indicators, signals, trend classification, AI commentary "
        "(Groq), portfolio analysis, backtesting and a TopBar market snapshot."
    ),
)


_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# =============================================================================
# Exception handlers
# =============================================================================


_ERROR_MAP: dict[type[TradingToolError], tuple[int, str]] = {
    InvalidSymbolError: (404, "INVALID_SYMBOL"),
    InsufficientDataError: (422, "INSUFFICIENT_DATA"),
    PortfolioError: (400, "INVALID_INPUT"),
    AIServiceError: (503, "AI_SERVICE_ERROR"),
    DataSourceError: (502, "DATA_SOURCE_ERROR"),
    CacheError: (500, "INTERNAL_ERROR"),
}


@app.exception_handler(TradingToolError)
async def _domain_error_handler(_request: Request, exc: TradingToolError) -> JSONResponse:
    status, code = _ERROR_MAP.get(type(exc), (500, "INTERNAL_ERROR"))
    if isinstance(exc, DataSourceError) and getattr(exc, "rate_limit", False):
        status, code = 429, "RATE_LIMIT_EXCEEDED"
    log.warning("%s [%d %s]: %s", type(exc).__name__, status, code, exc)
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": str(exc),
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(
    _request: Request, exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "INVALID_INPUT",
                "message": "request validation failed",
                "details": {"errors": exc.errors()},
            }
        },
    )


# =============================================================================
# Routes
# =============================================================================


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION)


_API_PREFIX = "/api"
app.include_router(ohlcv.router, prefix=_API_PREFIX, tags=["ohlcv"])
app.include_router(indicators.router, prefix=_API_PREFIX, tags=["indicators"])
app.include_router(signals.router, prefix=_API_PREFIX, tags=["signals"])
app.include_router(trend.router, prefix=_API_PREFIX, tags=["trend"])
app.include_router(ai.router, prefix=_API_PREFIX, tags=["ai"])
app.include_router(portfolio.router, prefix=_API_PREFIX, tags=["portfolio"])
app.include_router(backtest.router, prefix=_API_PREFIX, tags=["backtest"])
app.include_router(market.router, prefix=_API_PREFIX, tags=["market"])
