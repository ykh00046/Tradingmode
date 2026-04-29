"""Unit tests for ``core.backtest``."""

from __future__ import annotations

import math

import pytest

from core import backtest
from core.types.schemas import BacktestResult


def test_unknown_strategy_raises(trending_up_df) -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        backtest.run(trending_up_df, strategy="does_not_exist")


def test_run_returns_backtestresult(trending_up_df) -> None:
    result = backtest.run(trending_up_df, strategy="ma_cross", cash=1_000_000)
    assert isinstance(result, BacktestResult)


def test_metrics_are_finite_floats(trending_up_df) -> None:
    result = backtest.run(trending_up_df, strategy="ma_cross", cash=1_000_000)
    for field in (
        "total_return",
        "annual_return",
        "max_drawdown",
        "win_rate",
        "sharpe_ratio",
    ):
        v = getattr(result, field)
        assert isinstance(v, float)
        assert math.isfinite(v), f"{field} should be finite, got {v}"


def test_num_trades_non_negative(trending_up_df) -> None:
    result = backtest.run(trending_up_df, strategy="ma_cross", cash=1_000_000)
    assert result.num_trades >= 0


def test_equity_curve_length_reasonable(trending_up_df) -> None:
    result = backtest.run(trending_up_df, strategy="ma_cross", cash=1_000_000)
    # backtesting.py emits 1 equity point per bar, but with warm-up bars dropped
    # — accept anything between 50% of the input length and the full length.
    assert 0.5 * len(trending_up_df) <= len(result.equity_curve) <= len(trending_up_df)


def test_strategies_registry_contains_ma_cross() -> None:
    assert "ma_cross" in backtest.STRATEGIES
