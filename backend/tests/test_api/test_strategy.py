"""Integration tests for /api/strategy/* and /api/ai/strategy-coach."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


_BASE_REQUEST = {
    "market": "crypto",
    "symbol": "BTCUSDT",
    "interval": "1d",
    "start": 1704067200000,
    "end": 1721347200000,
    "split_ratio": 0.7,
    "cash": 1_000_000,
    "persist": False,                                  # don't pollute global iteration log
    "strategy": {
        "name": "MA Cross",
        "buy_when": "SMA_20 > SMA_60",
        "sell_when": "SMA_20 < SMA_60",
        "optimization_goal": "sharpe",
    },
}


# =============================================================================
# /api/strategy/builtins
# =============================================================================


def test_builtins_returns_indicator_catalogue(client) -> None:
    res = client.get("/api/strategy/builtins")
    assert res.status_code == 200, res.text
    body = res.json()
    names = {b["name"] for b in body["indicators"]}
    assert {"SMA", "RSI", "MACD", "Bollinger Bands", "ADX"}.issubset(names)
    assert "and" in body["operators"]
    assert "prev" in body["helpers"]


# =============================================================================
# /api/strategy/backtest — happy path
# =============================================================================


def test_backtest_returns_split_result(client, patch_fetch) -> None:
    res = client.post("/api/strategy/backtest", json=_BASE_REQUEST)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "is_result" in body
    assert "is_period_start" in body and isinstance(body["is_period_start"], int)
    assert body["costs_applied"]["commission_bps"] == pytest.approx(5.0)
    # OOS slice from 200-bar synthetic df is 60 bars → present.
    assert body["oos_result"] is not None
    assert isinstance(body["is_oos_gap_pct"], float)


def test_backtest_persists_iteration_when_requested(client, patch_fetch, monkeypatch, writable_tmp_dir) -> None:
    monkeypatch.setenv("ITERATION_LOG_DIR", str(writable_tmp_dir))
    body = dict(_BASE_REQUEST, persist=True)
    res = client.post("/api/strategy/backtest", json=body)
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["iteration_id"]
    assert payload["attempt_no"] == 1

    # second run → attempt_no increments
    body2 = dict(body, strategy={**body["strategy"], "name": "MA Cross v2"})
    res2 = client.post("/api/strategy/backtest", json=body2)
    assert res2.json()["attempt_no"] == 2


def test_backtest_rejects_invalid_expression(client, patch_fetch) -> None:
    body = dict(_BASE_REQUEST)
    body["strategy"] = {**body["strategy"], "buy_when": "RSI_14.__class__"}
    res = client.post("/api/strategy/backtest", json=body)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


def test_backtest_rejects_unknown_column(client, patch_fetch) -> None:
    body = dict(_BASE_REQUEST)
    body["strategy"] = {**body["strategy"], "buy_when": "MYSTERY > 0"}
    res = client.post("/api/strategy/backtest", json=body)
    assert res.status_code == 400


def test_backtest_validates_split_ratio(client) -> None:
    body = dict(_BASE_REQUEST, split_ratio=0.99)
    res = client.post("/api/strategy/backtest", json=body)
    assert res.status_code == 400


# =============================================================================
# /api/strategy/iterations
# =============================================================================


def test_iterations_returns_recent_attempts(
    client, patch_fetch, monkeypatch, writable_tmp_dir,
) -> None:
    monkeypatch.setenv("ITERATION_LOG_DIR", str(writable_tmp_dir))
    body = dict(_BASE_REQUEST, persist=True)
    client.post("/api/strategy/backtest", json=body)
    client.post(
        "/api/strategy/backtest",
        json=dict(body, strategy={**body["strategy"], "name": "v2"}),
    )
    res = client.get("/api/strategy/iterations", params={"symbol": "BTCUSDT", "interval": "1d"})
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    # Newest first
    assert rows[0]["attempt_no"] >= rows[1]["attempt_no"]


# =============================================================================
# /api/ai/strategy-coach
# =============================================================================


_VALID_COACH_RESPONSE = json.dumps(
    {
        "diagnosis": "추세 진입은 양호하나 이탈이 늦음.",
        "recommendations": [
            {
                "indicator": "ATR",
                "params": {"length": 14},
                "role": "exit_rule",
                "reason": "변동성 손절 추가",
                "expected_synergy": "MDD 개선",
                "sample_rule": "close < SMA_20 - 2 * ATR_14",
            },
            {
                "indicator": "RSI",
                "params": {"period": 14},
                "role": "filter",
                "reason": "과열 진입 회피",
                "expected_synergy": "엔트리 정밀화",
                "sample_rule": "RSI_14 < 70",
            },
        ],
        "warnings": ["IS 기간 짧음"],
    }
)


def _fake_groq(content: str) -> object:
    completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: completion)))


_COACH_BODY = {
    "strategy": _BASE_REQUEST["strategy"],
    "is_result": {
        "total_return": 12.4,
        "annual_return": 18.0,
        "max_drawdown": -7.5,
        "win_rate": 55.0,
        "sharpe_ratio": 0.7,
        "num_trades": 8,
    },
}


def test_coach_returns_recommendations(client, mocker, writable_tmp_dir) -> None:
    mocker.patch("core.strategy_coach.cache.cache_root", return_value=writable_tmp_dir)
    mocker.patch("core.ai_interpreter._client", return_value=_fake_groq(_VALID_COACH_RESPONSE))
    res = client.post("/api/ai/strategy-coach", json=_COACH_BODY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "추세" in body["diagnosis"]
    by_name = {r["indicator"]: r for r in body["recommendations"]}
    # ATR is not built in → flagged as unavailable
    assert by_name["ATR"]["available"] is False
    # RSI is built in → flagged as available
    assert by_name["RSI"]["available"] is True


def test_coach_503_when_key_missing(client, mocker, monkeypatch, writable_tmp_dir) -> None:
    mocker.patch("core.strategy_coach.cache.cache_root", return_value=writable_tmp_dir)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    res = client.post("/api/ai/strategy-coach", json=_COACH_BODY)
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "AI_SERVICE_ERROR"


# =============================================================================
# /api/trend?series=true
# =============================================================================


def test_trend_returns_series_when_requested(client, patch_fetch) -> None:
    params = {
        "market": "crypto",
        "symbol": "BTCUSDT",
        "interval": "1d",
        "start": 1704067200000,
        "end": 1721347200000,
        "series": True,
    }
    res = client.get("/api/trend", params=params)
    assert res.status_code == 200
    body = res.json()
    assert body["series"] is not None
    assert len(body["series"]) > 100
    states = {p["state"] for p in body["series"]}
    assert states.issubset({"uptrend", "downtrend", "sideways"})


def test_trend_omits_series_by_default(client, patch_fetch) -> None:
    params = {
        "market": "crypto",
        "symbol": "BTCUSDT",
        "interval": "1d",
        "start": 1704067200000,
        "end": 1721347200000,
    }
    res = client.get("/api/trend", params=params)
    assert res.status_code == 200
    assert res.json().get("series") is None
