"""Signal detection — runs on a DataFrame that already contains indicator columns.

The detection functions are deterministic and pure: same input always yields
identical output. Tests can rely on this.
"""

from __future__ import annotations

import pandas as pd

from core.types.schemas import Signal, SignalAction, SignalKind

# =============================================================================
# Helpers
# =============================================================================


def _signal_at(
    ts: pd.Timestamp,
    kind: SignalKind,
    action: SignalAction,
    price: float,
    detail: dict,
) -> Signal:
    return Signal(
        timestamp=ts,
        kind=kind,
        action=action,
        price=float(price),
        strength=1.0,        # v0.4 fixed; v2 will introduce per-kind formulas
        detail=detail,
    )


# =============================================================================
# MA cross (golden / death)
# =============================================================================


def detect_ma_cross(
    df: pd.DataFrame,
    short: int = 20,
    long: int = 60,
) -> list[Signal]:
    """Detect golden / death crosses between ``SMA_<short>`` and ``SMA_<long>``."""
    short_col = f"SMA_{short}"
    long_col = f"SMA_{long}"
    if short_col not in df.columns or long_col not in df.columns:
        return []

    s = df[short_col]
    l = df[long_col]  # noqa: E741 — convention in TA libs
    prev_s, prev_l = s.shift(1), l.shift(1)

    golden_mask = (prev_s <= prev_l) & (s > l)
    death_mask = (prev_s >= prev_l) & (s < l)

    out: list[Signal] = []
    for ts in df.index[golden_mask.fillna(False)]:
        out.append(
            _signal_at(
                ts,
                SignalKind.GOLDEN_CROSS,
                SignalAction.BUY,
                df.at[ts, "close"],
                {
                    "ma_short": float(s.loc[ts]),
                    "ma_long": float(l.loc[ts]),
                    "short_period": short,
                    "long_period": long,
                },
            )
        )
    for ts in df.index[death_mask.fillna(False)]:
        out.append(
            _signal_at(
                ts,
                SignalKind.DEATH_CROSS,
                SignalAction.SELL,
                df.at[ts, "close"],
                {
                    "ma_short": float(s.loc[ts]),
                    "ma_long": float(l.loc[ts]),
                    "short_period": short,
                    "long_period": long,
                },
            )
        )
    return out


# =============================================================================
# RSI overbought / oversold entry
# =============================================================================


def detect_rsi_signals(
    df: pd.DataFrame,
    period: int = 14,
    overbought: float = 70.0,
    oversold: float = 30.0,
) -> list[Signal]:
    """Detect entries above ``overbought`` and below ``oversold`` thresholds."""
    col = f"RSI_{period}"
    if col not in df.columns:
        return []

    rsi = df[col]
    prev = rsi.shift(1)

    overbought_entry = (prev <= overbought) & (rsi > overbought)
    oversold_entry = (prev >= oversold) & (rsi < oversold)

    out: list[Signal] = []
    for ts in df.index[overbought_entry.fillna(False)]:
        out.append(
            _signal_at(
                ts,
                SignalKind.RSI_OVERBOUGHT,
                SignalAction.SELL,
                df.at[ts, "close"],
                {"rsi": float(rsi.loc[ts]), "threshold": overbought},
            )
        )
    for ts in df.index[oversold_entry.fillna(False)]:
        out.append(
            _signal_at(
                ts,
                SignalKind.RSI_OVERSOLD,
                SignalAction.BUY,
                df.at[ts, "close"],
                {"rsi": float(rsi.loc[ts]), "threshold": oversold},
            )
        )
    return out


# =============================================================================
# RSI divergence (bull / bear)
# =============================================================================


def detect_rsi_divergence(
    df: pd.DataFrame,
    period: int = 14,
    lookback: int = 20,
) -> list[Signal]:
    """Detect bull/bear RSI divergence vs price using a rolling lookback window.

    Bull divergence: price prints a lower low while RSI prints a higher low.
    Bear divergence: price prints a higher high while RSI prints a lower high.

    For each bar starting at index ``2 * lookback`` we compare two adjacent
    windows of length ``lookback`` and emit at most one signal per bar.
    """
    col = f"RSI_{period}"
    if col not in df.columns or len(df) < 2 * lookback:
        return []

    close = df["close"].to_numpy()
    rsi = df[col].to_numpy()
    out: list[Signal] = []

    for i in range(2 * lookback, len(df)):
        win_a_start = i - 2 * lookback
        win_a_end = i - lookback
        win_b_end = i

        price_low_a = close[win_a_start:win_a_end].min()
        price_low_b = close[win_a_end:win_b_end].min()
        rsi_low_a = rsi[win_a_start:win_a_end].min()
        rsi_low_b = rsi[win_a_end:win_b_end].min()

        price_high_a = close[win_a_start:win_a_end].max()
        price_high_b = close[win_a_end:win_b_end].max()
        rsi_high_a = rsi[win_a_start:win_a_end].max()
        rsi_high_b = rsi[win_a_end:win_b_end].max()

        ts = df.index[i]
        # Bull divergence
        if price_low_b < price_low_a and rsi_low_b > rsi_low_a:
            out.append(
                _signal_at(
                    ts,
                    SignalKind.RSI_BULL_DIV,
                    SignalAction.BUY,
                    df.at[ts, "close"],
                    {
                        "price_low_prev": float(price_low_a),
                        "price_low_curr": float(price_low_b),
                        "rsi_low_prev": float(rsi_low_a),
                        "rsi_low_curr": float(rsi_low_b),
                    },
                )
            )
        # Bear divergence
        elif price_high_b > price_high_a and rsi_high_b < rsi_high_a:
            out.append(
                _signal_at(
                    ts,
                    SignalKind.RSI_BEAR_DIV,
                    SignalAction.SELL,
                    df.at[ts, "close"],
                    {
                        "price_high_prev": float(price_high_a),
                        "price_high_curr": float(price_high_b),
                        "rsi_high_prev": float(rsi_high_a),
                        "rsi_high_curr": float(rsi_high_b),
                    },
                )
            )
    return out


# =============================================================================
# MACD signal-line cross
# =============================================================================


def detect_macd_cross(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> list[Signal]:
    """Detect MACD vs signal-line crosses."""
    macd_col = f"MACD_{fast}_{slow}_{signal}"
    sig_col = f"MACDs_{fast}_{slow}_{signal}"
    if macd_col not in df.columns or sig_col not in df.columns:
        return []

    macd = df[macd_col]
    sig = df[sig_col]
    prev_macd, prev_sig = macd.shift(1), sig.shift(1)

    bull_mask = (prev_macd <= prev_sig) & (macd > sig)
    bear_mask = (prev_macd >= prev_sig) & (macd < sig)

    out: list[Signal] = []
    for ts in df.index[bull_mask.fillna(False)]:
        out.append(
            _signal_at(
                ts,
                SignalKind.MACD_BULL_CROSS,
                SignalAction.BUY,
                df.at[ts, "close"],
                {"macd": float(macd.loc[ts]), "signal": float(sig.loc[ts])},
            )
        )
    for ts in df.index[bear_mask.fillna(False)]:
        out.append(
            _signal_at(
                ts,
                SignalKind.MACD_BEAR_CROSS,
                SignalAction.SELL,
                df.at[ts, "close"],
                {"macd": float(macd.loc[ts]), "signal": float(sig.loc[ts])},
            )
        )
    return out


# =============================================================================
# Combined detection
# =============================================================================


def detect_all(df: pd.DataFrame) -> list[Signal]:
    """Run every detector and return signals sorted by timestamp ascending."""
    signals: list[Signal] = []
    signals.extend(detect_ma_cross(df))
    signals.extend(detect_rsi_signals(df))
    signals.extend(detect_rsi_divergence(df))
    signals.extend(detect_macd_cross(df))
    signals.sort(key=lambda s: s.timestamp)
    return signals
