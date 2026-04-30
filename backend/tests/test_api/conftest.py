"""Shared TestClient + fixture builders for API integration tests.

The Domain layer is exercised heavily in ``tests/test_*.py``. Here we mock
``data_loader.fetch`` (and friends) so route tests focus on:
- request/response shape
- status codes
- error → JSON mapping
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_synthetic_df(n: int = 200, start_price: float = 100.0) -> pd.DataFrame:
    """Build a deterministic OHLCV frame long enough for SMA_120 / ADX(14)."""
    rng = np.random.default_rng(0)
    base = np.linspace(start_price, start_price * 2.5, n)
    noise = rng.normal(0, 1.0, n)
    closes = base + noise
    opens = np.concatenate([[closes[0]], closes[:-1]])
    spread = np.maximum(np.abs(closes - opens) * 0.5, closes * 0.005)
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    return _make_synthetic_df()


@pytest.fixture
def patch_fetch(mocker, synthetic_df) -> None:
    """Replace ``core.data_loader.fetch`` everywhere it's imported."""
    targets = [
        "api.ohlcv.data_loader.fetch",
        "api.indicators.data_loader.fetch",
        "api.signals.data_loader.fetch",
        "api.trend.data_loader.fetch",
        "api.ai.data_loader.fetch",
        "api.backtest.data_loader.fetch",
    ]
    for t in targets:
        mocker.patch(t, return_value=(synthetic_df, True))
