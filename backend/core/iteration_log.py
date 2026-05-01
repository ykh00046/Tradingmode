"""Persistent iteration history — one parquet file per (symbol, interval).

Append-only log of every backtest attempt the user runs through the
strategy-coach UI. Used to populate the comparison table on the page and to
feed condensed context back into the AI coach prompt across iterations.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from core.types.errors import CacheError
from core.types.schemas import IterationEntry
from lib.logger import get_logger

log = get_logger(__name__)


# =============================================================================
# Paths
# =============================================================================


def _root() -> Path:
    """Resolve ``ITERATION_LOG_DIR`` (default ``./data/_iterations``)."""
    raw = os.environ.get("ITERATION_LOG_DIR", "./data/_iterations")
    root = Path(raw).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_iteration_path(symbol: str, interval: str) -> Path:
    """Sanitise path components and refuse anything that escapes the root.

    Same algorithm as ``lib.cache._safe_resolve`` but bound to a different
    root so the OHLCV cache and the iteration log can't pollute each other.
    """
    if "/" in interval or "\\" in interval or ".." in interval:
        raise CacheError(
            f"unsafe interval: {interval!r}",
            details={"symbol": symbol, "interval": interval},
        )
    safe_symbol = (
        symbol.replace("/", "_")
              .replace("\\", "_")
              .replace(":", "_")
              .replace("..", "_")
    )
    candidate = (_root() / f"{safe_symbol}_{interval}.parquet").resolve()
    try:
        candidate.relative_to(_root())
    except ValueError as e:
        raise CacheError(
            f"refusing to write outside iteration root: {candidate}",
            details={"symbol": symbol, "interval": interval, "resolved": str(candidate)},
        ) from e
    return candidate


# =============================================================================
# Read / append / compare
# =============================================================================


def _to_row(entry: IterationEntry) -> dict:
    row = asdict(entry)
    # parquet handles pd.Timestamp natively, but we normalise to UTC.
    ts = entry.timestamp
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    row["timestamp"] = ts
    return row


def _from_row(row: pd.Series) -> IterationEntry:
    return IterationEntry(
        iteration_id=str(row["iteration_id"]),
        symbol=str(row["symbol"]),
        interval=str(row["interval"]),
        attempt_no=int(row["attempt_no"]),
        strategy_def_json=str(row["strategy_def_json"]),
        is_total_return=float(row["is_total_return"]),
        oos_total_return=(
            None if pd.isna(row["oos_total_return"]) else float(row["oos_total_return"])
        ),
        is_sharpe=float(row["is_sharpe"]),
        oos_sharpe=None if pd.isna(row["oos_sharpe"]) else float(row["oos_sharpe"]),
        is_mdd=float(row["is_mdd"]),
        oos_mdd=None if pd.isna(row["oos_mdd"]) else float(row["oos_mdd"]),
        is_win_rate=float(row["is_win_rate"]),
        is_oos_gap_pct=(
            None if pd.isna(row["is_oos_gap_pct"]) else float(row["is_oos_gap_pct"])
        ),
        overfit_warning=bool(row["overfit_warning"]),
        optimization_goal=str(row["optimization_goal"]),
        coach_diagnosis=(
            None if pd.isna(row["coach_diagnosis"]) else str(row["coach_diagnosis"])
        ),
        applied_recommendation=(
            None
            if pd.isna(row["applied_recommendation"])
            else str(row["applied_recommendation"])
        ),
        timestamp=pd.Timestamp(row["timestamp"]),
    )


def append(entry: IterationEntry) -> Path:
    """Persist one attempt. Refuses duplicate ``iteration_id`` (idempotency
    is *not* a feature of this log — every attempt should have a fresh uuid)."""
    path = _safe_iteration_path(entry.symbol, entry.interval)
    new_row = pd.DataFrame([_to_row(entry)])

    if path.exists():
        try:
            existing = pd.read_parquet(path)
        except Exception as e:
            raise CacheError(
                f"failed to read existing iteration log: {path}",
                details={"path": str(path)},
            ) from e
        if entry.iteration_id in set(existing["iteration_id"].astype(str)):
            raise CacheError(
                f"duplicate iteration_id: {entry.iteration_id}",
                details={"path": str(path)},
            )
        combined = pd.concat([existing, new_row], ignore_index=True)
    else:
        combined = new_row

    combined = combined.sort_values("timestamp", kind="stable").reset_index(drop=True)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(path)
    except Exception as e:
        raise CacheError(
            f"failed to write iteration log: {path}",
            details={"path": str(path)},
        ) from e
    log.debug("iteration appended: %s (total=%d)", entry.iteration_id, len(combined))
    return path


def read(
    symbol: str,
    interval: str,
    limit: int = 50,
) -> list[IterationEntry]:
    """Return up to ``limit`` most-recent entries (timestamp desc)."""
    path = _safe_iteration_path(symbol, interval)
    if not path.exists():
        return []
    try:
        df = pd.read_parquet(path)
    except Exception as e:
        raise CacheError(
            f"failed to read iteration log: {path}",
            details={"path": str(path)},
        ) from e
    df = df.sort_values("timestamp", ascending=False).head(limit)
    return [_from_row(row) for _, row in df.iterrows()]


def compare(
    symbol: str,
    interval: str,
    iteration_ids: list[str],
) -> pd.DataFrame:
    """Filter the log down to the chosen attempts for side-by-side comparison."""
    path = _safe_iteration_path(symbol, interval)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    return df[df["iteration_id"].astype(str).isin(set(iteration_ids))].reset_index(drop=True)
