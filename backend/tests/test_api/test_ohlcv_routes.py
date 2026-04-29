"""Tests for the data-fetching routes: /ohlcv, /indicators, /signals, /trend."""

from __future__ import annotations


_BASE_PARAMS = dict(
    market="crypto",
    symbol="BTCUSDT",
    interval="1d",
    start=1704067200000,   # 2024-01-01
    end=1721347200000,     # 2024-07-19
)


# =============================================================================
# /ohlcv
# =============================================================================


def test_ohlcv_returns_candles(client, patch_fetch) -> None:
    res = client.get("/api/ohlcv", params=_BASE_PARAMS)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["market"] == "crypto"
    assert body["symbol"] == "BTCUSDT"
    assert len(body["candles"]) == 200
    first = body["candles"][0]
    for k in ("t", "o", "h", "l", "c", "v"):
        assert k in first
    assert isinstance(first["t"], int)


def test_ohlcv_validates_market(client) -> None:
    bad = dict(_BASE_PARAMS, market="forex")
    res = client.get("/api/ohlcv", params=bad)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_INPUT"


# =============================================================================
# /indicators
# =============================================================================


def test_indicators_returns_indicator_columns(client, patch_fetch) -> None:
    res = client.get("/api/indicators", params=_BASE_PARAMS)
    assert res.status_code == 200, res.text
    body = res.json()
    cols = set(body["indicators"])
    # All indicator families present (under whatever pandas-ta naming variant)
    assert any(c.startswith("SMA_") for c in cols)
    assert any(c.startswith("RSI_") for c in cols)
    assert any(c.startswith("MACD") for c in cols)
    assert any(c.startswith("BB") for c in cols)
    assert any(c.startswith("ADX") for c in cols)


# =============================================================================
# /signals
# =============================================================================


def test_signals_returns_list(client, patch_fetch) -> None:
    res = client.get("/api/signals", params=_BASE_PARAMS)
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body["signals"], list)
    if body["signals"]:
        s = body["signals"][0]
        assert "kind" in s and "action" in s and "timestamp" in s


# =============================================================================
# /trend
# =============================================================================


def test_trend_returns_classification(client, patch_fetch) -> None:
    res = client.get("/api/trend", params=_BASE_PARAMS)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["trend"] in {"uptrend", "downtrend", "sideways"}
    assert "ma_alignment" in body
