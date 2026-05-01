"""Strategy DSL evaluator + 70/30 split backtest runner.

Three responsibilities:
1. ``validate_expression`` — AST-level sandbox so user input cannot escape.
2. ``evaluate_rules`` — turn ``buy_when``/``sell_when`` into bool Series.
3. ``run_split`` — apply the strategy across a 70/30 IS/OOS slice and aggregate.

The engine is independent of ``backtesting.py``: we generate boolean entry/exit
signals ourselves and use the existing ``core.backtest`` wrapper for stats by
synthesising a tiny Strategy class on the fly. That keeps the eval surface
small (no callbacks into user code from inside backtesting.py).
"""

from __future__ import annotations

import ast
import os
from typing import Any

import pandas as pd

from core import backtest as core_backtest
from core.types.errors import InsufficientDataError, InvalidStrategyError
from core.types.schemas import (
    BacktestResult,
    BacktestSplitResult,
    BuiltinIndicator,
    Market,
    StrategyDef,
    TradingCosts,
)
from lib.logger import get_logger

log = get_logger(__name__)

# =============================================================================
# DSL allowlist
# =============================================================================

ALLOWED_FUNCTIONS: frozenset[str] = frozenset({"abs", "min", "max", "mean", "prev"})
ALLOWED_CONSTANTS: frozenset[str] = frozenset({"True", "False"})

# AST node types explicitly permitted. Everything else → InvalidStrategyError.
_ALLOWED_NODES: tuple = (
    ast.Expression,
    ast.Name,
    ast.Constant,
    ast.Load,
    # logical
    ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
    # arithmetic
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    # comparison
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    # function call (further restricted to ALLOWED_FUNCTIONS)
    ast.Call,
)

_FORBIDDEN_NODES_HINT: dict[type, str] = {
    ast.Attribute: "attribute access (`.foo`)",
    ast.Subscript: "subscript (`x[i]`)",
    ast.Lambda: "lambda",
    ast.ListComp: "list comprehension",
    ast.SetComp: "set comprehension",
    ast.DictComp: "dict comprehension",
    ast.GeneratorExp: "generator expression",
    ast.IfExp: "ternary `if-else`",
    ast.Starred: "* unpacking",
    ast.JoinedStr: "f-string",
    ast.NamedExpr: "walrus `:=`",
}


def _max_strategy_rules() -> int:
    """Read MAX_STRATEGY_RULES env (default 10)."""
    try:
        return int(os.environ.get("MAX_STRATEGY_RULES", "10"))
    except ValueError:
        return 10


def _count_logical_tokens(node: ast.AST) -> int:
    """Count and/or operands across the entire AST (BoolOp can have N children)."""
    count = 0
    for sub in ast.walk(node):
        if isinstance(sub, ast.BoolOp):
            # ``a and b and c`` is one BoolOp with 3 values → 2 conjunctions.
            count += max(0, len(sub.values) - 1)
    return count


def validate_expression(expr: str, allowed_columns: set[str]) -> None:
    """Refuse anything outside the allowlist. Raises ``InvalidStrategyError``.

    Allowed Names: ``allowed_columns`` ∪ ``ALLOWED_FUNCTIONS`` ∪ ``ALLOWED_CONSTANTS``.
    Allowed Calls: ``func`` must be a Name in ``ALLOWED_FUNCTIONS``.
    Constants must be int/float/bool — strings are rejected (no good reason
    to use them in a boolean rule, and they can ferry payloads).
    """
    if not expr or not expr.strip():
        raise InvalidStrategyError("expression is empty", details={"expr": expr})
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise InvalidStrategyError(
            f"syntax error: {e.msg}",
            details={"expr": expr, "offset": e.offset},
        ) from e

    allowed_names = allowed_columns | ALLOWED_FUNCTIONS | ALLOWED_CONSTANTS

    for node in ast.walk(tree):
        if isinstance(node, _ALLOWED_NODES):
            # Further per-node restrictions
            if isinstance(node, ast.Name) and node.id not in allowed_names:
                raise InvalidStrategyError(
                    f"unknown identifier: {node.id!r}",
                    details={"expr": expr, "token": node.id, "reason": "not in column/function allowlist"},
                )
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name):
                    raise InvalidStrategyError(
                        "only direct function calls allowed",
                        details={"expr": expr, "reason": "callable must be a bare name"},
                    )
                if node.func.id not in ALLOWED_FUNCTIONS:
                    raise InvalidStrategyError(
                        f"function not in allowlist: {node.func.id!r}",
                        details={"expr": expr, "token": node.func.id},
                    )
                # No keyword arguments — keeps prev(col, n) form predictable.
                if node.keywords:
                    raise InvalidStrategyError(
                        "keyword arguments not allowed",
                        details={"expr": expr, "function": node.func.id},
                    )
            if isinstance(node, ast.Constant):
                if not isinstance(node.value, (int, float, bool)):
                    raise InvalidStrategyError(
                        f"constant type not allowed: {type(node.value).__name__}",
                        details={"expr": expr, "value": repr(node.value)},
                    )
            continue

        # Anything not in _ALLOWED_NODES is out.
        hint = _FORBIDDEN_NODES_HINT.get(type(node), type(node).__name__)
        raise InvalidStrategyError(
            f"forbidden syntax: {hint}",
            details={"expr": expr, "node": type(node).__name__},
        )

    rules = _count_logical_tokens(tree)
    limit = _max_strategy_rules()
    if rules >= limit:
        raise InvalidStrategyError(
            f"too many and/or rules: {rules} >= limit {limit}",
            details={"expr": expr, "rule_count": rules, "limit": limit},
        )


# =============================================================================
# Rule evaluation
# =============================================================================


def _prev(series: pd.Series, n: int) -> pd.Series:
    """Helper exposed inside eval — equivalent to ``series.shift(n)``."""
    return series.shift(int(n))


def _eval_locals(df: pd.DataFrame) -> dict[str, Any]:
    """Build the ``local_dict`` for ``pandas.eval``."""
    locals_: dict[str, Any] = {col: df[col] for col in df.columns}
    # Built-in helpers exposed to the DSL.
    locals_["abs"] = abs
    locals_["min"] = min
    locals_["max"] = max
    locals_["mean"] = lambda *xs: sum(xs) / len(xs)
    locals_["prev"] = _prev
    locals_["True"] = True
    locals_["False"] = False
    return locals_


def _coerce_bool_series(value: Any, index: pd.Index) -> pd.Series:
    """Wrap any pandas-eval result into a bool Series aligned to ``index``."""
    if isinstance(value, pd.Series):
        return value.fillna(False).astype(bool).reindex(index, fill_value=False)
    # Scalar True/False applied uniformly.
    return pd.Series([bool(value)] * len(index), index=index)


def _eval_one(expr: str, df: pd.DataFrame) -> pd.Series:
    locals_ = _eval_locals(df)
    # ``engine='python'`` is required because our DSL allows function calls
    # (numexpr does not). Safety comes from the AST validator above, not from
    # the engine choice.
    try:
        result = pd.eval(expr, parser="pandas", engine="python", local_dict=locals_)
    except Exception as e:                                                   # pragma: no cover
        raise InvalidStrategyError(
            f"evaluation failed: {e}",
            details={"expr": expr, "type": type(e).__name__},
        ) from e
    return _coerce_bool_series(result, df.index)


def evaluate_rules(
    df: pd.DataFrame,
    buy_when: str,
    sell_when: str,
) -> tuple[pd.Series, pd.Series]:
    """Evaluate buy/sell expressions, returning aligned boolean Series."""
    cols = set(df.columns)
    validate_expression(buy_when, cols)
    validate_expression(sell_when, cols)
    return _eval_one(buy_when, df), _eval_one(sell_when, df)


# =============================================================================
# Trading costs
# =============================================================================


def apply_trading_costs(costs: TradingCosts, market: Market) -> float:
    """Combine commission + round-trip slippage + KR sell tax into a single
    fraction, since ``backtesting.py`` only accepts a single commission value.

    Round-trip → slippage counted twice (entry + exit). KR sell tax applies
    once (on the exit). The per-trade fee is therefore
    ``commission + 2*slippage + (kr_sell_tax if applicable)``.
    """
    total_bps = costs.commission_bps + 2 * costs.slippage_bps
    if market == Market.KR_STOCK and costs.apply_kr_tax:
        total_bps += costs.kr_sell_tax_bps
    return total_bps / 10_000.0


# =============================================================================
# Split + run
# =============================================================================

_MIN_OOS_BARS = 30


def split_70_30(
    df: pd.DataFrame, ratio: float = 0.7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Time-ordered split. Caller must compute indicators on the full df first
    so OOS bars inherit valid SMA_120/MACD values from the IS tail.
    """
    if not 0.5 < ratio < 0.95:
        raise ValueError(f"split ratio must be in (0.5, 0.95): {ratio}")
    n = int(len(df) * ratio)
    return df.iloc[:n].copy(), df.iloc[n:].copy()


def _build_signal_strategy(entry: pd.Series, exit_: pd.Series, holding_max: int | None):
    """Construct a backtesting.Strategy class driven by precomputed signals.

    Indexed lookups are done by integer position so the class doesn't need to
    know about the original DatetimeIndex. ``holding_max`` enforces forced
    closure after N bars — useful when the user's ``sell_when`` rarely fires.
    """
    from backtesting import Strategy

    entry_arr = entry.to_numpy(dtype=bool)
    exit_arr = exit_.to_numpy(dtype=bool)

    class _SignalStrategy(Strategy):
        def init(self) -> None:                                              # pragma: no cover
            self._entry_bars = 0

        def next(self) -> None:                                              # pragma: no cover
            i = len(self.data) - 1                                            # current bar index
            if self.position:
                self._entry_bars += 1
                hit_exit = i < len(exit_arr) and exit_arr[i]
                hit_max = holding_max is not None and self._entry_bars >= holding_max
                if hit_exit or hit_max:
                    self.position.close()
                    self._entry_bars = 0
            else:
                if i < len(entry_arr) and entry_arr[i]:
                    self.buy()
                    self._entry_bars = 0

    _SignalStrategy.__name__ = "SignalStrategy"
    return _SignalStrategy


def run_with_strategy_def(
    df: pd.DataFrame,
    strategy_def: StrategyDef,
    cash: float,
    market: Market,
) -> BacktestResult:
    """Evaluate the user's rules then delegate to the existing backtest wrapper."""
    if df.empty:
        raise InsufficientDataError(
            "empty dataframe — nothing to backtest",
            details={"strategy": strategy_def.name},
        )
    entry, exit_ = evaluate_rules(df, strategy_def.buy_when, strategy_def.sell_when)
    strategy_cls = _build_signal_strategy(entry, exit_, strategy_def.holding_max_bars)
    commission = apply_trading_costs(strategy_def.costs, market)
    return core_backtest.run(df, strategy=strategy_cls, cash=cash, commission=commission)


def _safe_pct(value: float | None) -> float:
    return float(value) if value is not None else 0.0


def run_split(
    df: pd.DataFrame,
    strategy_def: StrategyDef,
    market: Market,
    cash: float = 10_000_000,
    ratio: float = 0.7,
) -> BacktestSplitResult:
    """Run the strategy on IS, then OOS, and compute the gap warning.

    Indicators must already be computed on ``df``. OOS slices shorter than
    ``_MIN_OOS_BARS`` degrade gracefully — IS result is returned with
    ``oos_result=None`` and a user-visible warning.
    """
    df_is, df_oos = split_70_30(df, ratio=ratio)
    if len(df_is) == 0:
        raise InsufficientDataError(
            "in-sample slice is empty after split",
            details={"len_total": len(df), "ratio": ratio},
        )

    is_result = run_with_strategy_def(df_is, strategy_def, cash, market)
    is_period = (df_is.index[0], df_is.index[-1])

    warnings: list[str] = []
    if len(df_oos) < _MIN_OOS_BARS:
        warnings.append(
            f"OOS 봉 < {_MIN_OOS_BARS} ({len(df_oos)}) — 검증 스킵"
        )
        return BacktestSplitResult(
            is_result=is_result,
            oos_result=None,
            is_period=is_period,
            oos_period=None,
            is_oos_gap_pct=None,
            overfit_warning=False,
            costs_applied=strategy_def.costs,
            warnings=warnings,
        )

    oos_result = run_with_strategy_def(df_oos, strategy_def, cash, market)
    oos_period = (df_oos.index[0], df_oos.index[-1])

    gap = _safe_pct(is_result.total_return) - _safe_pct(oos_result.total_return)
    overfit = abs(gap) > 30.0
    if overfit:
        warnings.append(f"IS-OOS gap {gap:.1f}% — 과적합 위험")
    return BacktestSplitResult(
        is_result=is_result,
        oos_result=oos_result,
        is_period=is_period,
        oos_period=oos_period,
        is_oos_gap_pct=gap,
        overfit_warning=overfit,
        costs_applied=strategy_def.costs,
        warnings=warnings,
    )


# =============================================================================
# Built-in indicator catalogue (UI autocompletion + AI prompt context)
# =============================================================================

BUILTIN_INDICATORS: list[BuiltinIndicator] = [
    BuiltinIndicator(
        name="SMA",
        columns=["SMA_5", "SMA_20", "SMA_60", "SMA_120"],
        params={"periods": [5, 20, 60, 120]},
        description="단순 이동평균 (5/20/60/120봉)",
        category="trend",
    ),
    BuiltinIndicator(
        name="RSI",
        columns=["RSI_14"],
        params={"period": 14},
        description="Relative Strength Index — 과매수/과매도",
        category="momentum",
    ),
    BuiltinIndicator(
        name="MACD",
        columns=["MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9"],
        params={"fast": 12, "slow": 26, "signal": 9},
        description="MACD 라인/시그널/히스토그램",
        category="momentum",
    ),
    BuiltinIndicator(
        name="Bollinger Bands",
        columns=["BBL_20_2.0_2.0", "BBM_20_2.0_2.0", "BBU_20_2.0_2.0"],
        params={"length": 20, "std": 2.0},
        description="볼린저 밴드 — 변동성 + 평균회귀",
        category="volatility",
    ),
    BuiltinIndicator(
        name="ADX",
        columns=["ADX_14", "DMP_14", "DMN_14"],
        params={"length": 14},
        description="추세 강도 지수 + 방향성 지표",
        category="trend",
    ),
]


SUPPORTED_OPERATORS: list[str] = [
    "+", "-", "*", "/", "//", "%", "**",
    "<", "<=", "==", "!=", ">", ">=",
    "and", "or", "not",
]


SUPPORTED_HELPERS: list[str] = sorted(ALLOWED_FUNCTIONS)
