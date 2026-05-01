"""Domain-level exceptions used across all layers.

Cross-cut: imported by core, api, lib alike. No external dependencies.
"""

from __future__ import annotations


class TradingToolError(Exception):
    """Base for all domain errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.details: dict = details or {}


class DataSourceError(TradingToolError):
    """External market-data API call failed (network, timeout, server error).

    Set ``rate_limit=True`` to signal that a rate limit was the cause —
    the FastAPI handler maps this to HTTP 429 instead of 502.
    """

    def __init__(
        self,
        message: str,
        *,
        rate_limit: bool = False,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details)
        self.rate_limit = rate_limit


class InvalidSymbolError(TradingToolError):
    """Symbol does not exist or is malformed."""


class InsufficientDataError(TradingToolError):
    """Not enough OHLCV bars to compute the requested indicator.

    Example: caller asks for SMA_120 but only 100 bars are available.
    """


class CacheError(TradingToolError):
    """Cache read/write failed.

    Backend should attempt to degrade gracefully (bypass cache and re-fetch)
    rather than surface this to the user.
    """


class AIServiceError(TradingToolError):
    """Groq API call failed (auth, rate limit, network).

    AI commentary is auxiliary — the rest of the analysis must keep working
    even when this is raised. The HTTP layer maps to 503.
    """


class PortfolioError(TradingToolError):
    """Portfolio input/analysis error (CSV parse, missing field, bad value)."""


class InvalidStrategyError(TradingToolError):
    """User-defined strategy expression failed validation.

    Raised when:
    - AST contains a forbidden node type (Lambda, Attribute, Subscript, ...).
    - A Name references a column that doesn't exist on the dataframe.
    - A Call references a function outside the allowlist.
    - and/or token count exceeds ``MAX_STRATEGY_RULES``.

    Always includes ``details`` with at least ``{"reason": ..., "expr": ...}``.
    """
