"""Shared pytest fixtures — synthetic OHLCV data generators.

All generators are deterministic (seeded) so failures are reproducible.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest


def _make_ohlcv(closes: np.ndarray, *, start: str = "2024-01-01") -> pd.DataFrame:
    """Build a daily OHLCV DataFrame from a close-price series.

    Highs and lows are derived as small offsets so that ``high >= max(open, close)``
    and ``low <= min(open, close)`` hold. Volume is constant.
    """
    n = len(closes)
    idx = pd.date_range(start=start, periods=n, freq="D")
    opens = np.concatenate([[closes[0]], closes[:-1]])
    spread = np.maximum(np.abs(closes - opens) * 0.5, closes * 0.005)
    highs = np.maximum(opens, closes) + spread
    lows = np.minimum(opens, closes) - spread
    volumes = np.full(n, 1_000_000.0)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=idx,
    )


@pytest.fixture
def trending_up_df() -> pd.DataFrame:
    """200 bars of strong uptrend — close from 100 to ~250 with low noise."""
    rng = np.random.default_rng(42)
    base = np.linspace(100, 250, 200)
    noise = rng.normal(0, 1.0, 200)
    return _make_ohlcv(base + noise)


@pytest.fixture
def trending_down_df() -> pd.DataFrame:
    """200 bars of strong downtrend — close from 250 to ~100."""
    rng = np.random.default_rng(43)
    base = np.linspace(250, 100, 200)
    noise = rng.normal(0, 1.0, 200)
    return _make_ohlcv(base + noise)


@pytest.fixture
def sideways_df() -> pd.DataFrame:
    """200 bars of sideways action — close oscillating around 150."""
    rng = np.random.default_rng(44)
    base = 150 + 5 * np.sin(np.linspace(0, 8 * np.pi, 200))
    noise = rng.normal(0, 0.5, 200)
    return _make_ohlcv(base + noise)


@pytest.fixture
def golden_cross_df() -> pd.DataFrame:
    """Series engineered so that SMA_20 crosses SMA_60 from below.

    First 90 bars decline (SMA_20 < SMA_60), then strong recovery causes
    the cross.
    """
    decline = np.linspace(200, 100, 90)
    recovery = np.linspace(100, 220, 110)
    return _make_ohlcv(np.concatenate([decline, recovery]))


@pytest.fixture
def death_cross_df() -> pd.DataFrame:
    """Mirror of golden_cross_df."""
    rise = np.linspace(100, 200, 90)
    fall = np.linspace(200, 80, 110)
    return _make_ohlcv(np.concatenate([rise, fall]))


@pytest.fixture
def short_df() -> pd.DataFrame:
    """Only 50 bars — too short for SMA_120 / ADX."""
    rng = np.random.default_rng(45)
    closes = 100 + np.cumsum(rng.normal(0, 1, 50))
    return _make_ohlcv(closes)


@pytest.fixture
def writable_tmp_dir() -> Path:
    root = Path.home() / ".codex" / "memories" / "backend-test-tmp"
    path = root / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
