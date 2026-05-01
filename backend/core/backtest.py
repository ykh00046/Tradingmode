"""Backtesting wrapper around ``backtesting.py``.

The library expects CamelCase columns (``Open``, ``High``, …) — we translate
internally so callers always work with our canonical lowercase OHLCV.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from core.types.schemas import BacktestResult


def _to_backtesting_df(df: pd.DataFrame) -> pd.DataFrame:
    """Convert lowercase OHLCV → CamelCase columns required by backtesting.py."""
    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    return df.rename(columns=rename)


# =============================================================================
# Built-in strategies
# =============================================================================


def _build_ma_cross_strategy(short: int = 20, long: int = 60) -> type:
    """Construct a MA-cross Strategy class bound to the given periods.

    A factory is used because backtesting.py reads strategy parameters from
    class attributes; closing over ``short`` / ``long`` would otherwise force
    callers to subclass. The class is created lazily so that environments
    without ``backtesting`` installed can still import this module.
    """
    from backtesting import Strategy
    from backtesting.lib import crossover

    class _MaCross(Strategy):
        n_short = short
        n_long = long

        def init(self) -> None:                                             # pragma: no cover
            close = pd.Series(self.data.Close)
            self.sma_short = self.I(lambda: close.rolling(self.n_short).mean())
            self.sma_long = self.I(lambda: close.rolling(self.n_long).mean())

        def next(self) -> None:                                             # pragma: no cover
            if crossover(self.sma_short, self.sma_long):
                self.buy()
            elif crossover(self.sma_long, self.sma_short):
                self.position.close()

    _MaCross.__name__ = f"MaCross_{short}_{long}"
    return _MaCross


# Strategy name registry — exposed so the API layer can validate user input.
STRATEGIES: dict[str, Any] = {
    "ma_cross": _build_ma_cross_strategy,
}


# =============================================================================
# Result conversion
# =============================================================================


def _safe_float(x: Any, default: float = 0.0) -> float:
    """``backtesting.py`` returns NaN for some metrics on tiny datasets."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _convert_result(stats: pd.Series, df_index: pd.DatetimeIndex) -> BacktestResult:
    """Map a ``backtesting.py`` Series of stats to our ``BacktestResult``."""
    equity_curve = stats["_equity_curve"]["Equity"]
    trades = stats["_trades"]

    # Reindex equity_curve to original timestamps for cleaner plotting downstream
    if not isinstance(equity_curve.index, pd.DatetimeIndex):
        equity_curve = equity_curve.set_axis(df_index[: len(equity_curve)])

    return BacktestResult(
        total_return=_safe_float(stats.get("Return [%]")),
        annual_return=_safe_float(stats.get("Return (Ann.) [%]")),
        max_drawdown=_safe_float(stats.get("Max. Drawdown [%]")),
        win_rate=_safe_float(stats.get("Win Rate [%]")),
        sharpe_ratio=_safe_float(stats.get("Sharpe Ratio")),
        num_trades=int(_safe_float(stats.get("# Trades"))),
        equity_curve=equity_curve,
        trades=trades,
    )


# =============================================================================
# Public API
# =============================================================================


def run(
    df: pd.DataFrame,
    strategy: str | type = "ma_cross",
    cash: float = 10_000_000,
    commission: float = 0.0005,
    **strategy_params: Any,
) -> BacktestResult:
    """Backtest ``strategy`` against ``df`` and return a normalised result.

    Parameters
    ----------
    df:
        OHLCV with our canonical lowercase columns and ``DatetimeIndex``.
    strategy:
        Either a strategy name registered in ``STRATEGIES`` or a fully
        constructed ``backtesting.Strategy`` subclass.
    cash, commission:
        Forwarded to ``backtesting.Backtest``. Commission is per-trade as
        a fraction (0.0005 = 5 bps).
    strategy_params:
        Forwarded to the strategy factory (e.g. ``short=20, long=60``).
    """
    from backtesting import Backtest

    if isinstance(strategy, str):
        if strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy: {strategy}. Known: {list(STRATEGIES)}")
        strategy_cls = STRATEGIES[strategy](**strategy_params)
    else:
        strategy_cls = strategy

    bt_df = _to_backtesting_df(df)
    bt = Backtest(bt_df, strategy_cls, cash=cash, commission=commission, exclusive_orders=True)
    stats = bt.run()
    return _convert_result(stats, df.index)                                  # type: ignore[arg-type]
