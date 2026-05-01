"""AI strategy coach — wraps the Groq client to suggest complementary indicators.

Inputs: user's ``StrategyDef`` + ``BacktestResult`` (in-sample only) + optimisation
goal + the catalogue of built-in indicators. Output: ``CoachResponse`` with a
short diagnosis, three boost recommendations, and optional warnings.

Cache key is sha256 of a stable JSON dump (sort_keys=True) over a 5-scalar IS
summary, the strategy definition, the goal, and the model name. Equity curves
and trades are deliberately excluded so small numerical fluctuations don't
explode the cache.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from typing import Any

import pandas as pd

from core import ai_interpreter                                              # reuse Groq _client + cache helpers
from core.types.errors import AIServiceError
from core.types.schemas import (
    BacktestResult,
    BuiltinIndicator,
    CoachRecommendation,
    CoachResponse,
    StrategyDef,
)
from lib import cache
from lib.logger import get_logger

log = get_logger(__name__)

DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 900


SYSTEM_PROMPT_COACH = """당신은 정량 트레이딩 전략 컨설턴트입니다.
사용자가 정의한 전략의 In-sample 백테스트 결과를 보고 다음을 수행합니다:
1. 약점을 1~2문장으로 진단 (diagnosis)
2. 보완할 지표 3개를 추천 (recommendations) — 각각 role 명시
   - role 값: "filter", "exit_rule", "entry_filter", "sizing"
3. 우려점 1~2개 (warnings) — 과적합/시장 변화 등

규칙:
- 사용자가 제공하는 builtin_indicators 외 지표를 추천해도 좋습니다
  (없으면 사용자가 직접 추가 구현해야 함)
- 추측·예측·"수익 보장" 표현 절대 금지
- 한국어로 답변
- 각 추천에는 sample_rule 가급적 포함 (실제 적용할 expression 문자열, 예: "ATR_14 < 0.05 * close")
- 응답은 JSON 한 객체. 다른 텍스트 없음
- JSON 스키마:
  {
    "diagnosis": str,
    "recommendations": [
      {"indicator": str, "params": {...}, "role": str,
       "reason": str, "expected_synergy": str, "sample_rule": str|null}
    ],
    "warnings": [str]
  }"""


# =============================================================================
# Prompt construction
# =============================================================================


def _is_summary(result: BacktestResult) -> dict[str, float | int]:
    """Stable 5-scalar summary used both for the prompt and the cache key.

    Excludes equity_curve and trades so small numerical jitter doesn't
    invalidate the cache for what is effectively the same result.
    """
    return {
        "total_return": result.total_return,
        "annual_return": result.annual_return,
        "max_drawdown": result.max_drawdown,
        "win_rate": result.win_rate,
        "sharpe_ratio": result.sharpe_ratio,
        "num_trades": result.num_trades,
    }


def _strategy_payload(strategy: StrategyDef) -> dict[str, Any]:
    """Serialise the user strategy for prompt + cache key construction.

    Important: ``buy_when`` / ``sell_when`` end up as JSON string values, never
    interpolated into the system prompt. That's our prompt-injection defence.
    """
    payload = asdict(strategy)
    # Enums become their .value through asdict() since we used (str, Enum).
    # IndicatorConfig is a TypedDict (already plain dict) → asdict leaves it alone.
    return payload


def build_prompt(
    strategy: StrategyDef,
    is_result: BacktestResult,
    builtin_indicators: list[BuiltinIndicator],
    history_summary: list[dict] | None = None,
) -> tuple[str, str]:
    """Return ``(system_prompt, user_message)`` for the Groq chat call."""
    user_payload = {
        "strategy": _strategy_payload(strategy),
        "is_result_summary": _is_summary(is_result),
        "goal": strategy.optimization_goal.value,
        "builtin_indicators": [
            {"name": b.name, "columns": b.columns, "category": b.category}
            for b in builtin_indicators
        ],
        "history_summary": history_summary or [],
    }
    user_message = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
    return SYSTEM_PROMPT_COACH, user_message


# =============================================================================
# Cache key
# =============================================================================


def _cache_key(
    strategy: StrategyDef,
    is_result: BacktestResult,
    model: str,
) -> str:
    payload = json.dumps(
        {
            "strategy": _strategy_payload(strategy),
            "is_summary": _is_summary(is_result),
            "goal": strategy.optimization_goal.value,
            "model": model,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _cache_path(key: str) -> Any:
    """AI coach responses live alongside ai_interpreter cache, in a subdir."""
    return cache._safe_resolve(f"_coach/{key}.json")                          # type: ignore[attr-defined]


# =============================================================================
# Response parsing
# =============================================================================


_VALID_ROLES = {"filter", "exit_rule", "entry_filter", "sizing"}


def parse_response(
    content: str,
    builtin_names: set[str],
    model: str,
) -> CoachResponse:
    """Validate the LLM's JSON response and convert into ``CoachResponse``.

    Raises ``AIServiceError`` if the model doesn't follow the schema. The
    builtin_names set is used to flag each recommendation as available/unknown.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise AIServiceError(
            f"coach returned non-JSON: {content[:160]}",
            details={"raw_head": content[:200]},
        ) from e

    if not isinstance(data, dict):
        raise AIServiceError("coach response is not a JSON object", details={"got": type(data).__name__})

    diagnosis = data.get("diagnosis")
    recs_raw = data.get("recommendations")
    warnings_raw = data.get("warnings", [])
    if not isinstance(diagnosis, str) or not diagnosis.strip():
        raise AIServiceError("missing or empty 'diagnosis'")
    if not isinstance(recs_raw, list) or not recs_raw:
        raise AIServiceError("missing or empty 'recommendations'")

    recs: list[CoachRecommendation] = []
    for raw in recs_raw:
        if not isinstance(raw, dict):
            continue
        indicator = str(raw.get("indicator") or "").strip()
        if not indicator:
            continue
        role = raw.get("role") or "filter"
        if role not in _VALID_ROLES:
            role = "filter"
        params = raw.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        sample_rule = raw.get("sample_rule")
        if sample_rule is not None and not isinstance(sample_rule, str):
            sample_rule = None
        recs.append(
            CoachRecommendation(
                indicator=indicator,
                params=params,
                role=role,                                                   # type: ignore[arg-type]
                reason=str(raw.get("reason") or ""),
                expected_synergy=str(raw.get("expected_synergy") or ""),
                available=indicator in builtin_names,
                sample_rule=sample_rule,
            )
        )

    if not recs:
        raise AIServiceError("no usable recommendations parsed from coach response")

    warnings_list = [str(w) for w in warnings_raw] if isinstance(warnings_raw, list) else []

    return CoachResponse(
        diagnosis=diagnosis,
        recommendations=recs,
        warnings=warnings_list,
        model=model,
        generated_at=pd.Timestamp.now(tz="UTC"),
    )


# =============================================================================
# Public entry-point
# =============================================================================


def _resolve_model(model: str | None) -> str:
    return (
        model
        or os.environ.get("STRATEGY_COACH_MODEL")
        or os.environ.get("GROQ_MODEL")
        or "llama-3.3-70b-versatile"
    )


def _hydrate_cached(payload: dict, model: str) -> CoachResponse:
    """Reconstruct CoachResponse from a previously cached JSON payload."""
    recs = [
        CoachRecommendation(
            indicator=r["indicator"],
            params=r.get("params", {}) or {},
            role=r["role"],
            reason=r.get("reason", ""),
            expected_synergy=r.get("expected_synergy", ""),
            available=bool(r.get("available", False)),
            sample_rule=r.get("sample_rule"),
        )
        for r in payload.get("recommendations", [])
    ]
    return CoachResponse(
        diagnosis=payload["diagnosis"],
        recommendations=recs,
        warnings=list(payload.get("warnings", [])),
        model=payload.get("model", model),
        generated_at=pd.Timestamp(payload["generated_at"]),
    )


def _serialise(resp: CoachResponse) -> dict:
    return {
        "diagnosis": resp.diagnosis,
        "recommendations": [
            {
                "indicator": r.indicator,
                "params": r.params,
                "role": r.role,
                "reason": r.reason,
                "expected_synergy": r.expected_synergy,
                "available": r.available,
                "sample_rule": r.sample_rule,
            }
            for r in resp.recommendations
        ],
        "warnings": list(resp.warnings),
        "model": resp.model,
        "generated_at": resp.generated_at.isoformat(),
        "disclaimer": resp.disclaimer,
    }


def recommend(
    strategy: StrategyDef,
    is_result: BacktestResult,
    builtin_indicators: list[BuiltinIndicator],
    history_summary: list[dict] | None = None,
    model: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
) -> CoachResponse:
    """Generate or load a cached coach response.

    Reuses ``ai_interpreter._client`` for the Groq SDK so we don't duplicate
    auth handling. Cache miss → LLM call; cache hit → instant.
    """
    resolved_model = _resolve_model(model)
    key = _cache_key(strategy, is_result, resolved_model)
    path = _cache_path(key)

    cached = cache.load_ai(path)
    if cached is not None:
        log.debug("coach cache hit: %s", key)
        return _hydrate_cached(cached, resolved_model)

    log.info("coach call: %s (model=%s)", strategy.name, resolved_model)
    client = ai_interpreter._client(resolved_model)                          # type: ignore[attr-defined]
    system_prompt, user_message = build_prompt(
        strategy, is_result, builtin_indicators, history_summary
    )

    try:
        completion = client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=DEFAULT_MAX_TOKENS,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise AIServiceError(
            f"Groq coach call failed: {e}",
            details={"type": type(e).__name__, "model": resolved_model},
        ) from e

    content = completion.choices[0].message.content or ""
    if not content:
        raise AIServiceError("coach returned empty content")

    builtin_names = {b.name for b in builtin_indicators}
    response = parse_response(content, builtin_names, resolved_model)

    cache.save_ai(path, _serialise(response))
    return response
