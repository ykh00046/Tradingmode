"""Unit tests for ``core.ai_interpreter``.

Groq client is monkey-patched so no real API calls are made.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from core import ai_interpreter
from core.types.errors import AIServiceError
from core.types.schemas import AICommentary, Signal, SignalAction, SignalKind


def _signal() -> Signal:
    return Signal(
        timestamp=pd.Timestamp("2024-06-15"),
        kind=SignalKind.GOLDEN_CROSS,
        action=SignalAction.BUY,
        price=68500.0,
        strength=1.0,
        detail={"ma_short": 67200, "ma_long": 66800},
    )


def _df_with_indicators() -> pd.DataFrame:
    idx = pd.date_range("2024-06-01", periods=20, freq="D")
    return pd.DataFrame(
        {
            "close": [68500.0] * 20,
            "RSI_14": [56.0] * 20,
            "SMA_20": [67200.0] * 20,
            "SMA_60": [66800.0] * 20,
            "MACD_12_26_9": [12.5] * 20,
            "MACDs_12_26_9": [10.0] * 20,
            "ADX_14": [28.5] * 20,
            "BBU_20_2.0": [70000.0] * 20,
            "BBL_20_2.0": [65000.0] * 20,
        },
        index=idx,
    )


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


def _fake_groq_client(content: str) -> object:
    """Build an object that mimics ``groq.Groq`` enough for our code path."""
    completion = _FakeCompletion(content)
    chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: completion))
    return SimpleNamespace(chat=chat)


# =============================================================================
# Happy path
# =============================================================================


def test_interpret_signal_parses_json(mocker, tmp_path) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=tmp_path)
    payload = json.dumps(
        {
            "summary": "단기/중기 MA 상향 교차",
            "detail": "SMA20이 SMA60을 상향 돌파했고 ADX 28.5로 추세 강도가 충분합니다.",
            "confidence": "medium",
        }
    )
    mocker.patch(
        "core.ai_interpreter._client",
        return_value=_fake_groq_client(payload),
    )

    result = ai_interpreter.interpret_signal(_signal(), _df_with_indicators(), "BTCUSDT")
    assert isinstance(result, AICommentary)
    assert "MA" in result.summary
    assert result.confidence == "medium"
    assert result.signal_kind == SignalKind.GOLDEN_CROSS
    assert "투자 자문" in result.disclaimer


# =============================================================================
# Cache
# =============================================================================


def test_cache_hit_avoids_second_call(mocker, tmp_path) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=tmp_path)
    payload = json.dumps(
        {"summary": "X", "detail": "Y", "confidence": "high"}
    )
    spy_factory = mocker.patch(
        "core.ai_interpreter._client",
        return_value=_fake_groq_client(payload),
    )

    sig = _signal()
    df = _df_with_indicators()
    ai_interpreter.interpret_signal(sig, df, "BTCUSDT")
    ai_interpreter.interpret_signal(sig, df, "BTCUSDT")

    # _client should be invoked exactly once — second call hits the disk cache.
    assert spy_factory.call_count == 1


# =============================================================================
# Error handling
# =============================================================================


def test_invalid_json_raises_ai_service_error(mocker, tmp_path) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=tmp_path)
    mocker.patch(
        "core.ai_interpreter._client",
        return_value=_fake_groq_client("not JSON"),
    )
    with pytest.raises(AIServiceError):
        ai_interpreter.interpret_signal(_signal(), _df_with_indicators(), "BTCUSDT")


def test_missing_field_raises_ai_service_error(mocker, tmp_path) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=tmp_path)
    mocker.patch(
        "core.ai_interpreter._client",
        return_value=_fake_groq_client('{"summary": "x", "detail": "y"}'),
    )
    with pytest.raises(AIServiceError):
        ai_interpreter.interpret_signal(_signal(), _df_with_indicators(), "BTCUSDT")


def test_unknown_confidence_is_coerced_to_medium(mocker, tmp_path) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=tmp_path)
    payload = json.dumps(
        {"summary": "x", "detail": "y", "confidence": "very-high"}
    )
    mocker.patch(
        "core.ai_interpreter._client",
        return_value=_fake_groq_client(payload),
    )
    out = ai_interpreter.interpret_signal(_signal(), _df_with_indicators(), "BTCUSDT")
    assert out.confidence == "medium"


def test_missing_api_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(AIServiceError, match="GROQ_API_KEY"):
        ai_interpreter._client("any-model")


# =============================================================================
# Batch
# =============================================================================


def test_batch_with_empty_list_returns_empty() -> None:
    assert ai_interpreter.interpret_signals_batch([], _df_with_indicators(), "BTCUSDT") == []
