"""Tests for POST /api/ai/explain.

The Groq client is replaced with a fake completion so no network calls happen.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


def _fake_groq(content: str) -> object:
    completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: completion)))


_REQUEST_BODY = {
    "market": "crypto",
    "symbol": "BTCUSDT",
    "interval": "1d",
    "signal_kind": "golden_cross",
    "timestamp": 1709251200000,    # 2024-03-01
    "price": 65000.0,
}


@pytest.fixture
def writable_cache_dir() -> Path:
    root = Path.home() / ".codex" / "memories" / "backend-ai-test-cache"
    path = root / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_ai_explain_returns_commentary(client, patch_fetch, mocker, writable_cache_dir) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=writable_cache_dir)
    payload = json.dumps(
        {"summary": "MA 상향 교차", "detail": "ADX 충분.", "confidence": "medium"}
    )
    mocker.patch("core.ai_interpreter._client", return_value=_fake_groq(payload))

    res = client.post("/api/ai/explain", json=_REQUEST_BODY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["summary"] == "MA 상향 교차"
    assert body["confidence"] == "medium"
    assert body["disclaimer"]
    assert isinstance(body["timestamp"], int)


def test_ai_explain_missing_key_returns_503(
    client, patch_fetch, mocker, monkeypatch, writable_cache_dir,
) -> None:
    mocker.patch("core.ai_interpreter.cache.cache_root", return_value=writable_cache_dir)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    res = client.post("/api/ai/explain", json=_REQUEST_BODY)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "AI_SERVICE_ERROR"


def test_ai_explain_validates_payload(client) -> None:
    bad = {**_REQUEST_BODY}
    bad.pop("price")
    res = client.post("/api/ai/explain", json=bad)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"
