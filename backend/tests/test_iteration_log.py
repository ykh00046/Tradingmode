"""Tests for ``core.iteration_log`` parquet history."""

from __future__ import annotations

from uuid import uuid4

import pandas as pd
import pytest

from core import iteration_log
from core.types.errors import CacheError
from core.types.schemas import IterationEntry


def _entry(symbol: str = "BTCUSDT", **overrides) -> IterationEntry:
    base = dict(
        iteration_id=uuid4().hex,
        symbol=symbol,
        interval="1d",
        attempt_no=1,
        strategy_def_json='{"name":"x"}',
        is_total_return=12.5,
        oos_total_return=8.0,
        is_sharpe=0.9,
        oos_sharpe=0.4,
        is_mdd=-7.0,
        oos_mdd=-9.0,
        is_win_rate=58.0,
        is_oos_gap_pct=4.5,
        overfit_warning=False,
        optimization_goal="sharpe",
        coach_diagnosis=None,
        applied_recommendation=None,
        timestamp=pd.Timestamp("2026-04-30T10:00:00", tz="UTC"),
    )
    base.update(overrides)
    return IterationEntry(**base)


@pytest.fixture
def isolated_log_dir(monkeypatch, writable_tmp_dir):
    monkeypatch.setenv("ITERATION_LOG_DIR", str(writable_tmp_dir))
    return writable_tmp_dir


# =============================================================================
# append + read
# =============================================================================


def test_append_creates_file_and_round_trips(isolated_log_dir) -> None:
    e1 = _entry()
    iteration_log.append(e1)
    rows = iteration_log.read("BTCUSDT", "1d")
    assert len(rows) == 1
    got = rows[0]
    assert got.iteration_id == e1.iteration_id
    assert got.is_total_return == pytest.approx(12.5)
    assert got.oos_total_return == pytest.approx(8.0)


def test_append_handles_partial_oos_none(isolated_log_dir) -> None:
    e = _entry(
        oos_total_return=None, oos_sharpe=None, oos_mdd=None, is_oos_gap_pct=None,
    )
    iteration_log.append(e)
    rows = iteration_log.read("BTCUSDT", "1d")
    assert rows[0].oos_total_return is None
    assert rows[0].oos_sharpe is None


def test_append_orders_by_timestamp(isolated_log_dir) -> None:
    older = _entry(timestamp=pd.Timestamp("2026-01-01T00:00:00", tz="UTC"), attempt_no=1)
    newer = _entry(timestamp=pd.Timestamp("2026-04-30T00:00:00", tz="UTC"), attempt_no=2)
    iteration_log.append(newer)
    iteration_log.append(older)
    rows = iteration_log.read("BTCUSDT", "1d")
    # read() returns newest first; the parquet file itself is sorted ascending.
    assert rows[0].attempt_no == 2
    assert rows[1].attempt_no == 1


def test_append_rejects_duplicate_iteration_id(isolated_log_dir) -> None:
    e = _entry()
    iteration_log.append(e)
    with pytest.raises(CacheError, match="duplicate"):
        iteration_log.append(e)


def test_read_missing_file_returns_empty(isolated_log_dir) -> None:
    assert iteration_log.read("MISSING", "1d") == []


def test_read_limits_results(isolated_log_dir) -> None:
    for i in range(5):
        iteration_log.append(
            _entry(
                attempt_no=i,
                timestamp=pd.Timestamp("2026-04-01T00:00:00", tz="UTC")
                + pd.Timedelta(hours=i),
            )
        )
    assert len(iteration_log.read("BTCUSDT", "1d", limit=3)) == 3


# =============================================================================
# compare
# =============================================================================


def test_compare_filters_by_iteration_id(isolated_log_dir) -> None:
    a = _entry(attempt_no=1)
    b = _entry(attempt_no=2)
    c = _entry(attempt_no=3)
    for e in (a, b, c):
        iteration_log.append(e)
    df = iteration_log.compare("BTCUSDT", "1d", [a.iteration_id, c.iteration_id])
    assert len(df) == 2
    assert set(df["attempt_no"].astype(int)) == {1, 3}


def test_compare_missing_file_returns_empty(isolated_log_dir) -> None:
    assert iteration_log.compare("MISSING", "1d", ["whatever"]).empty


# =============================================================================
# Path safety
# =============================================================================


def test_safe_path_rejects_traversal(isolated_log_dir) -> None:
    with pytest.raises(CacheError, match="unsafe"):
        iteration_log._safe_iteration_path("BTCUSDT", "../etc")
