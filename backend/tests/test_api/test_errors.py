"""Tests for the global exception handler — domain exceptions → JSON."""

from __future__ import annotations

from core.types.errors import (
    AIServiceError,
    DataSourceError,
    InsufficientDataError,
    InvalidSymbolError,
)


_PARAMS = dict(
    market="crypto",
    symbol="BTCUSDT",
    interval="1d",
    start=1704067200000,
    end=1706659200000,
)


def test_invalid_symbol_maps_to_404(client, mocker) -> None:
    mocker.patch("api.ohlcv.data_loader.fetch", side_effect=InvalidSymbolError("nope"))
    res = client.get("/api/ohlcv", params=_PARAMS)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "INVALID_SYMBOL"


def test_insufficient_data_maps_to_422(client, mocker) -> None:
    mocker.patch(
        "api.indicators.data_loader.fetch",
        side_effect=InsufficientDataError("too short", details={"required": 120, "actual": 50}),
    )
    res = client.get("/api/indicators", params=_PARAMS)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "INSUFFICIENT_DATA"
    assert res.json()["error"]["details"]["required"] == 120


def test_rate_limit_maps_to_429(client, mocker) -> None:
    mocker.patch(
        "api.signals.data_loader.fetch",
        side_effect=DataSourceError("binance 429", rate_limit=True),
    )
    res = client.get("/api/signals", params=_PARAMS)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_data_source_error_maps_to_502(client, mocker) -> None:
    mocker.patch(
        "api.trend.data_loader.fetch",
        side_effect=DataSourceError("upstream timeout"),
    )
    res = client.get("/api/trend", params=_PARAMS)
    assert res.status_code == 502
    assert res.json()["error"]["code"] == "DATA_SOURCE_ERROR"
