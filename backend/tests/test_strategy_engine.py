"""Unit tests for ``core.strategy_engine``.

Focus: the AST sandbox + rule evaluation + 70/30 split. Backtest run is
covered indirectly via ``run_split`` against a synthetic uptrend DF.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core import indicators, strategy_engine
from core.types.errors import InsufficientDataError, InvalidStrategyError
from core.types.schemas import (
    BacktestSplitResult,
    Market,
    OptimizationGoal,
    StrategyDef,
    TradingCosts,
)


# =============================================================================
# validate_expression — happy path
# =============================================================================


def test_validate_accepts_simple_comparison() -> None:
    strategy_engine.validate_expression("RSI_14 < 30", {"RSI_14"})


def test_validate_accepts_logical_combination() -> None:
    strategy_engine.validate_expression(
        "RSI_14 < 30 and ADX_14 > 25", {"RSI_14", "ADX_14"}
    )


def test_validate_accepts_arithmetic_and_helpers() -> None:
    strategy_engine.validate_expression(
        "SMA_20 - SMA_60 > abs(SMA_60 - SMA_120)",
        {"SMA_20", "SMA_60", "SMA_120"},
    )


def test_validate_accepts_prev_helper() -> None:
    strategy_engine.validate_expression("RSI_14 > prev(RSI_14, 1)", {"RSI_14"})


# =============================================================================
# validate_expression — sandbox enforcement
# =============================================================================


def test_validate_rejects_attribute_access() -> None:
    with pytest.raises(InvalidStrategyError, match="forbidden syntax"):
        strategy_engine.validate_expression("RSI_14.__class__", {"RSI_14"})


def test_validate_rejects_subscript() -> None:
    with pytest.raises(InvalidStrategyError, match="forbidden syntax"):
        strategy_engine.validate_expression("RSI_14[0]", {"RSI_14"})


def test_validate_rejects_lambda() -> None:
    with pytest.raises(InvalidStrategyError):
        strategy_engine.validate_expression("(lambda: True)()", set())


def test_validate_rejects_unknown_function() -> None:
    with pytest.raises(InvalidStrategyError, match="not in allowlist"):
        strategy_engine.validate_expression("eval('1+1')", set())


def test_validate_rejects_unknown_column() -> None:
    with pytest.raises(InvalidStrategyError, match="unknown identifier"):
        strategy_engine.validate_expression("MYSTERY > 0", {"RSI_14"})


def test_validate_rejects_string_constant() -> None:
    with pytest.raises(InvalidStrategyError, match="constant type"):
        strategy_engine.validate_expression("RSI_14 == 'foo'", {"RSI_14"})


def test_validate_rejects_walrus() -> None:
    with pytest.raises(InvalidStrategyError, match="walrus"):
        strategy_engine.validate_expression("(x := RSI_14) > 30", {"RSI_14"})


def test_validate_rejects_too_many_rules(monkeypatch) -> None:
    monkeypatch.setenv("MAX_STRATEGY_RULES", "2")
    with pytest.raises(InvalidStrategyError, match="too many"):
        strategy_engine.validate_expression(
            "RSI_14 < 30 and ADX_14 > 25 and SMA_20 > SMA_60",
            {"RSI_14", "ADX_14", "SMA_20", "SMA_60"},
        )


def test_validate_rejects_empty() -> None:
    with pytest.raises(InvalidStrategyError, match="empty"):
        strategy_engine.validate_expression("   ", set())


# =============================================================================
# evaluate_rules
# =============================================================================


def _toy_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {"close": range(10), "RSI_14": [50, 25, 28, 35, 80, 75, 50, 20, 90, 50]},
        index=idx,
    )


def test_evaluate_rules_returns_aligned_bool_series() -> None:
    df = _toy_df()
    entry, exit_ = strategy_engine.evaluate_rules(df, "RSI_14 < 30", "RSI_14 > 70")
    assert entry.dtype == bool
    assert exit_.dtype == bool
    assert entry.index.equals(df.index)
    assert int(entry.sum()) == 3                      # bars at 25, 28, 20
    assert int(exit_.sum()) == 3                      # bars at 80, 75, 90


def test_evaluate_rules_handles_prev() -> None:
    df = _toy_df()
    entry, _ = strategy_engine.evaluate_rules(
        df, "RSI_14 > prev(RSI_14, 1)", "False"
    )
    assert entry.iloc[0] is False or bool(entry.iloc[0]) is False  # NaN → False after fillna


# =============================================================================
# trading costs
# =============================================================================


def test_apply_trading_costs_kr_with_tax() -> None:
    costs = TradingCosts(commission_bps=5, slippage_bps=2, kr_sell_tax_bps=18, apply_kr_tax=True)
    fee = strategy_engine.apply_trading_costs(costs, Market.KR_STOCK)
    # 5 + 2*2 + 18 = 27 bp = 0.0027
    assert fee == pytest.approx(0.0027)


def test_apply_trading_costs_kr_without_tax() -> None:
    costs = TradingCosts(commission_bps=5, slippage_bps=2, apply_kr_tax=False)
    fee = strategy_engine.apply_trading_costs(costs, Market.KR_STOCK)
    assert fee == pytest.approx(0.0009)


def test_apply_trading_costs_crypto_ignores_kr_tax() -> None:
    costs = TradingCosts(commission_bps=5, slippage_bps=2, kr_sell_tax_bps=18, apply_kr_tax=True)
    fee = strategy_engine.apply_trading_costs(costs, Market.CRYPTO)
    assert fee == pytest.approx(0.0009)               # 5 + 4 = 9 bp


# =============================================================================
# split_70_30
# =============================================================================


def test_split_default_ratio_is_70_30() -> None:
    df = pd.DataFrame({"close": range(100)})
    is_, oos = strategy_engine.split_70_30(df)
    assert len(is_) == 70
    assert len(oos) == 30


def test_split_rejects_extreme_ratios() -> None:
    df = pd.DataFrame({"close": range(100)})
    with pytest.raises(ValueError):
        strategy_engine.split_70_30(df, ratio=0.99)


# =============================================================================
# run_split — end-to-end
# =============================================================================


def test_run_split_uptrend_produces_results(trending_up_df: pd.DataFrame) -> None:
    df = indicators.compute(trending_up_df)
    strat = StrategyDef(
        name="MA Cross test",
        buy_when="SMA_20 > SMA_60",
        sell_when="SMA_20 < SMA_60",
        costs=TradingCosts(),
        optimization_goal=OptimizationGoal.SHARPE,
    )
    result = strategy_engine.run_split(df, strat, market=Market.CRYPTO, cash=1_000_000)
    assert isinstance(result, BacktestSplitResult)
    assert result.oos_result is not None
    assert result.is_oos_gap_pct is not None
    # Both legs must produce finite stats.
    for r in (result.is_result, result.oos_result):
        for f in ("total_return", "sharpe_ratio", "max_drawdown"):
            assert isinstance(getattr(r, f), float)


def test_run_split_skips_oos_when_too_short(short_df: pd.DataFrame) -> None:
    """``short_df`` has 50 bars → OOS slice (15) < MIN_OOS_BARS (30)."""
    # Need indicators present so rules can reference them. SMA_20 is fine for 50 bars.
    df = indicators.add_sma(short_df, periods=[20])
    strat = StrategyDef(
        name="trivial",
        buy_when="close > SMA_20",
        sell_when="close < SMA_20",
    )
    result = strategy_engine.run_split(df, strat, market=Market.CRYPTO, cash=1_000_000)
    assert result.oos_result is None
    assert result.oos_period is None
    assert result.is_oos_gap_pct is None
    assert any("OOS" in w for w in result.warnings)


def test_run_split_empty_df_raises() -> None:
    empty = pd.DataFrame(
        {"open": [], "high": [], "low": [], "close": [], "volume": []},
        index=pd.DatetimeIndex([]),
    )
    strat = StrategyDef(name="x", buy_when="True", sell_when="False")
    with pytest.raises(InsufficientDataError):
        strategy_engine.run_split(empty, strat, market=Market.CRYPTO)


# =============================================================================
# Builtins catalogue
# =============================================================================


def test_builtin_indicators_cover_all_columns_emitted_by_compute(
    trending_up_df: pd.DataFrame,
) -> None:
    """Every indicator column produced by ``indicators.compute`` should be
    discoverable through the catalogue (otherwise the UI/AI cannot reference
    it by name)."""
    out = indicators.compute(trending_up_df)
    catalog = {col for ind in strategy_engine.BUILTIN_INDICATORS for col in ind.columns}
    for col in out.columns:
        if col in {"open", "high", "low", "close", "volume"}:
            continue
        assert col in catalog, f"{col} missing from BUILTIN_INDICATORS"
