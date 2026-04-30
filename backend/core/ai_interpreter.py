"""Groq LLM signal interpreter.

Wraps the Groq Python SDK (``/groq/groq-python``) to produce Korean natural-
language commentary for a detected ``Signal``. Results are cached on disk by
``(symbol, signal_kind, timestamp_ms, model)`` so identical signals do not
re-trigger an LLM call.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import fields as dataclass_fields
from typing import Any

import pandas as pd

from core.types.errors import AIServiceError
from core.types.schemas import AICommentary, Signal, SignalKind
from lib import cache
from lib.logger import get_logger

log = get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================


DEFAULT_MODEL = "llama-3.3-70b-versatile"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 600


SYSTEM_PROMPT = """당신은 한국어로 답하는 정량 트레이딩 분석가입니다.
사용자가 제공하는 신호와 지표 수치만을 근거로 *간결하게* 해설합니다.
규칙:
1. 추측 / 예측 / 권유 표현 금지 ("매수해야 한다" 등 절대 사용 X).
2. 제공받은 수치만 사용. 외부 정보 가정 금지.
3. 응답은 항상 JSON 객체 한 개. 다른 텍스트 없음.
4. JSON 스키마: {"summary": str, "detail": str, "confidence": "low"|"medium"|"high"}
5. summary는 1문장(40자 내), detail은 2~4문장, confidence는 지표 값들의 일관성으로 산정."""


_DEFAULT_DISCLAIMER = next(
    f.default for f in dataclass_fields(AICommentary) if f.name == "disclaimer"
)


# =============================================================================
# Prompt construction
# =============================================================================


def _round_or_dash(x: Any, n: int = 2) -> str:
    """Format an indicator value, falling back to '-' for None/NaN."""
    if x is None:
        return "-"
    try:
        f = float(x)
    except (TypeError, ValueError):
        return "-"
    if pd.isna(f):
        return "-"
    return f"{f:.{n}f}"


def _build_user_prompt(
    signal: Signal,
    df_window: pd.DataFrame,
    symbol: str,
) -> str:
    """Assemble the user prompt with structured indicator values.

    Note: ``signal.detail`` already contains values relevant to the signal kind;
    we additionally include MA / RSI / MACD / ADX / BB at the signal bar so the
    model has full context.
    """
    if signal.timestamp in df_window.index:
        bar = df_window.loc[signal.timestamp]
    else:
        bar = df_window.iloc[-1]

    fields = {
        "symbol": symbol,
        "kind": signal.kind.value,
        "action": signal.action.value,
        "timestamp": signal.timestamp.isoformat(),
        "price": _round_or_dash(signal.price),
        "rsi_14": _round_or_dash(bar.get("RSI_14")),
        "sma_20": _round_or_dash(bar.get("SMA_20")),
        "sma_60": _round_or_dash(bar.get("SMA_60")),
        "macd": _round_or_dash(bar.get("MACD_12_26_9")),
        "macd_signal": _round_or_dash(bar.get("MACDs_12_26_9")),
        "adx_14": _round_or_dash(bar.get("ADX_14")),
        # pandas-ta 0.4.x: column names include the std value twice (legacy quirk)
        "bb_upper": _round_or_dash(bar.get("BBU_20_2.0_2.0")),
        "bb_lower": _round_or_dash(bar.get("BBL_20_2.0_2.0")),
    }

    return (
        f"신호 정보: {json.dumps(fields, ensure_ascii=False)}\n"
        f"위 데이터만 근거로 JSON 객체를 생성하세요."
    )


# =============================================================================
# Single signal — sync interpretation with cache
# =============================================================================


def _client(model: str) -> Any:
    """Lazy-construct a Groq client."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise AIServiceError("GROQ_API_KEY not set — AI commentary disabled")
    try:
        from groq import Groq
    except ImportError as e:                                                 # pragma: no cover
        raise AIServiceError("groq package is not installed") from e
    return Groq(api_key=api_key)


def _parse_response(content: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise AIServiceError(
            f"LLM did not return JSON: {content[:200]}",
            details={"raw": content},
        ) from e
    for k in ("summary", "detail", "confidence"):
        if k not in data:
            raise AIServiceError(
                f"LLM JSON missing key '{k}': {data}",
                details={"received_keys": list(data)},
            )
    if data["confidence"] not in {"low", "medium", "high"}:
        # Coerce instead of failing — model may use synonyms
        data["confidence"] = "medium"
    return data


def _commentary_from_dict(
    payload: dict,
    signal: Signal,
    model: str,
) -> AICommentary:
    return AICommentary(
        signal_kind=signal.kind,
        timestamp=signal.timestamp,
        summary=str(payload["summary"]),
        detail=str(payload["detail"]),
        confidence=payload["confidence"],                                    # type: ignore[arg-type]
        model=model,
        generated_at=pd.Timestamp.now(tz='UTC'),
    )


def interpret_signal(
    signal: Signal,
    df_window: pd.DataFrame,
    symbol: str,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> AICommentary:
    """Generate or load cached commentary for a single signal.

    Cache key = ``(symbol, signal.kind, signal.timestamp_ms, model)``.
    """
    ts_ms = int(signal.timestamp.timestamp() * 1000)
    path = cache.ai_cache_path(symbol, signal.kind.value, ts_ms, model)

    cached = cache.load_ai(path)
    if cached is not None:
        log.debug("ai cache hit: %s %s @ %s", symbol, signal.kind.value, signal.timestamp)
        return AICommentary(
            signal_kind=SignalKind(cached["signal_kind"]),
            timestamp=pd.Timestamp(cached["timestamp"]),
            summary=cached["summary"],
            detail=cached["detail"],
            confidence=cached["confidence"],
            model=cached["model"],
            generated_at=pd.Timestamp(cached["generated_at"]),
            disclaimer=cached.get("disclaimer", _DEFAULT_DISCLAIMER),
        )

    log.info("ai call: %s %s @ %s (model=%s)", symbol, signal.kind.value, signal.timestamp, model)
    client = _client(model)
    user_prompt = _build_user_prompt(signal, df_window, symbol)

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=DEFAULT_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise AIServiceError(
            f"Groq call failed: {e}",
            details={"type": type(e).__name__, "model": model},
        ) from e

    content = completion.choices[0].message.content
    if not content:
        raise AIServiceError("Groq returned empty content")

    payload = _parse_response(content)
    commentary = _commentary_from_dict(payload, signal, model)

    cache.save_ai(
        path,
        {
            "signal_kind": commentary.signal_kind.value,
            "timestamp": commentary.timestamp.isoformat(),
            "summary": commentary.summary,
            "detail": commentary.detail,
            "confidence": commentary.confidence,
            "model": commentary.model,
            "generated_at": commentary.generated_at.isoformat(),
            "disclaimer": commentary.disclaimer,
        },
    )
    return commentary


# =============================================================================
# Batch — concurrent with semaphore
# =============================================================================


async def _interpret_async(
    signals: list[Signal],
    df: pd.DataFrame,
    symbol: str,
    sem: asyncio.Semaphore,
    model: str,
    temperature: float,
) -> list[AICommentary]:
    """Run ``interpret_signal`` concurrently in threads, gated by ``sem``."""
    loop = asyncio.get_event_loop()

    async def _one(sig: Signal) -> AICommentary:
        async with sem:
            return await loop.run_in_executor(
                None,
                interpret_signal,
                sig,
                df,
                symbol,
                model,
                temperature,
            )

    return await asyncio.gather(*(_one(s) for s in signals))


def interpret_signals_batch(
    signals: list[Signal],
    df: pd.DataFrame,
    symbol: str,
    max_concurrent: int = 5,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
) -> list[AICommentary]:
    """Sync wrapper around ``_interpret_async`` for use in Streamlit/FastAPI sync handlers.

    Honours Groq free-tier rate limits via ``asyncio.Semaphore(max_concurrent)``.
    Cache hits are essentially free; only fresh calls compete for the semaphore.
    """
    if not signals:
        return []
    sem = asyncio.Semaphore(max_concurrent)
    return asyncio.run(
        _interpret_async(signals, df, symbol, sem, model, temperature)
    )
