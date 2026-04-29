"""Filesystem cache for OHLCV (parquet) and AI commentary (JSON).

Path safety: every cache operation resolves to a path *under* ``CACHE_DIR``;
attempts to escape via ``..`` raise ``CacheError``.

Behaviour: I/O failures degrade gracefully — callers can decide whether to
fall back to direct fetch or surface the error. A bare ``except`` here would
hide bugs, so we let ``CacheError`` propagate and let the caller handle it.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from core.types.errors import CacheError
from lib.logger import get_logger

log = get_logger(__name__)


# =============================================================================
# Paths
# =============================================================================


def cache_root() -> Path:
    """Root of the on-disk cache. Honors ``CACHE_DIR`` env (default: ./data)."""
    root = Path(os.environ.get("CACHE_DIR", "./data")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_resolve(relative: str) -> Path:
    """Resolve a relative cache path, refusing any path that escapes the root."""
    root = cache_root()
    p = (root / relative).resolve()
    try:
        p.relative_to(root)
    except ValueError as e:
        raise CacheError(
            f"refusing to access path outside cache root: {relative}",
            details={"resolved": str(p), "root": str(root)},
        ) from e
    return p


# =============================================================================
# OHLCV (parquet) cache
# =============================================================================


def ohlcv_cache_path(market: str, symbol: str, interval: str, start: str, end: str) -> Path:
    return _safe_resolve(f"{market}/{symbol}/{interval}/{start}_{end}.parquet")


def load_ohlcv(path: Path) -> pd.DataFrame | None:
    """Return cached OHLCV or ``None`` if not present.

    Raises ``CacheError`` only on actual I/O / corruption errors.
    """
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        log.debug("cache hit: %s", path)
        return df
    except Exception as e:
        raise CacheError(f"failed to read parquet cache: {path}", details={"path": str(path)}) from e


def save_ohlcv(path: Path, df: pd.DataFrame) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path)
        log.debug("cache save: %s (%d rows)", path, len(df))
    except Exception as e:
        raise CacheError(f"failed to write parquet cache: {path}", details={"path": str(path)}) from e


def load_or_fetch_ohlcv(
    path: Path,
    fetch_fn: Callable[[], pd.DataFrame],
) -> pd.DataFrame:
    """Return cached DataFrame or call ``fetch_fn`` and cache the result."""
    cached = load_ohlcv(path)
    if cached is not None:
        return cached
    df = fetch_fn()
    save_ohlcv(path, df)
    return df


# =============================================================================
# AI commentary (JSON) cache
# =============================================================================


def ai_cache_path(symbol: str, signal_kind: str, timestamp_ms: int, model: str) -> Path:
    safe_model = model.replace("/", "_").replace(":", "_")
    return _safe_resolve(f"_ai/{symbol}/{signal_kind}/{timestamp_ms}_{safe_model}.json")


def _json_default(obj: Any) -> Any:
    """JSON encoder fallback for dataclasses, datetime, pd.Timestamp."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    raise TypeError(f"unserialisable: {type(obj)}")


def load_ai(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise CacheError(f"failed to read AI cache: {path}", details={"path": str(path)}) from e


def save_ai(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        raise CacheError(f"failed to write AI cache: {path}", details={"path": str(path)}) from e
