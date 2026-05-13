"""FastAPI application entry-point.

Run from the ``backend/`` directory:

    uvicorn main:app --reload --port 8000

OpenAPI docs are auto-served at ``/docs``.
"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env before any module that reads env vars.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from api import ai, backtest, indicators, market, ohlcv, portfolio, signals, strategy, trend
from api.schemas import HealthResponse
from core.types.errors import (
    AIServiceError,
    CacheError,
    DataSourceError,
    InsufficientDataError,
    InvalidStrategyError,
    InvalidSymbolError,
    PortfolioError,
    TradingToolError,
)
from lib.logger import get_logger

# Bumped from 0.4.1 to reflect three shipped PDCA cycles since the original
# trading-analysis-tool baseline (rsi-price-bands → ux-improvements →
# longer-intervals) plus the comprehensive-review fixes.
VERSION = "0.9.0"
_STARTED_AT = time.monotonic()

log = get_logger(__name__)


# Cache the disk-write probe so /api/health stays cheap under load —
# without this, every request paid ~100ms for write+unlink. 5s TTL is short
# enough to detect a permission flip within one polling cycle.
_CACHE_WRITABLE_TTL_SEC = 5.0
_cache_writable_cached: tuple[float, bool] | None = None


def _cache_writable() -> bool:
    """Probe whether the OHLCV cache directory is writable. Result cached
    for ``_CACHE_WRITABLE_TTL_SEC`` so high-frequency /api/health pollers
    don't incur per-request disk IO."""
    global _cache_writable_cached
    now = time.monotonic()
    if _cache_writable_cached and (now - _cache_writable_cached[0]) < _CACHE_WRITABLE_TTL_SEC:
        return _cache_writable_cached[1]
    try:
        from lib import cache

        root = cache.cache_root()
        probe = root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        ok = True
    except Exception:
        ok = False
    _cache_writable_cached = (now, ok)
    return ok


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


_cors_env = os.environ.get("CORS_ORIGINS")
_cors_origins = [
    o.strip()
    for o in (_cors_env or "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000").split(",")
    if o.strip()
]
if _cors_env is None:
    log.warning(
        "CORS_ORIGINS env not set — falling back to localhost dev origins. "
        "Set CORS_ORIGINS to a comma-separated origin list before deploying to prod."
    )
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
    InvalidStrategyError: (400, "INVALID_INPUT"),
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
    """Self-diagnosis endpoint — `status` for liveness, additional fields for
    operational sanity checks (deploy verification, on-call triage)."""
    return HealthResponse(
        status="ok",
        version=VERSION,
        uptime_seconds=round(time.monotonic() - _STARTED_AT, 1),
        groq_configured=bool(os.environ.get("GROQ_API_KEY")),
        cache_writable=_cache_writable(),
        cors_origins_count=len(_cors_origins),
    )


_API_PREFIX = "/api"
app.include_router(ohlcv.router, prefix=_API_PREFIX, tags=["ohlcv"])
app.include_router(indicators.router, prefix=_API_PREFIX, tags=["indicators"])
app.include_router(signals.router, prefix=_API_PREFIX, tags=["signals"])
app.include_router(trend.router, prefix=_API_PREFIX, tags=["trend"])
app.include_router(ai.router, prefix=_API_PREFIX, tags=["ai"])
app.include_router(portfolio.router, prefix=_API_PREFIX, tags=["portfolio"])
app.include_router(backtest.router, prefix=_API_PREFIX, tags=["backtest"])
app.include_router(market.router, prefix=_API_PREFIX, tags=["market"])
app.include_router(strategy.router, prefix=_API_PREFIX, tags=["strategy"])
