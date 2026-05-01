"""Unit tests for ``core.data_loader``.

Adapters and the cache layer are mocked so these run without network access
or pandas-ta.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core import data_loader
from core.types.schemas import FetchRequest, Interval, Market


def _fake_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [95.0] * 10,
            "close": [102.0] * 10,
            "volume": [1000.0] * 10,
        },
        index=idx,
    )


def _make_request(market: Market = Market.CRYPTO) -> FetchRequest:
    return FetchRequest(
        market=market,
        symbol="BTCUSDT",
        interval=Interval.D1,
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-10"),
    )


def test_cache_miss_calls_adapter_and_saves(mocker, writable_tmp_dir) -> None:
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download", return_value=fake)
    krx_dl = mocker.patch("core.data_loader.krx_adapter.download")

    result, cache_hit = data_loader.fetch(_make_request(Market.CRYPTO))

    assert bin_dl.call_count == 1
    assert krx_dl.call_count == 0
    assert cache_hit is False
    pd.testing.assert_frame_equal(result, fake)


def test_cache_hit_skips_adapter(mocker, writable_tmp_dir) -> None:
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download", return_value=fake)

    # First call populates cache, second call should hit it.
    data_loader.fetch(_make_request(Market.CRYPTO))
    bin_dl.reset_mock()

    _, cache_hit = data_loader.fetch(_make_request(Market.CRYPTO))
    assert bin_dl.call_count == 0
    assert cache_hit is True


def test_routes_kr_market_to_krx_adapter(mocker, writable_tmp_dir) -> None:
    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    fake = _fake_df()
    bin_dl = mocker.patch("core.data_loader.binance_adapter.download")
    krx_dl = mocker.patch("core.data_loader.krx_adapter.download", return_value=fake)

    req = FetchRequest(
        market=Market.KR_STOCK,
        symbol="005930",
        interval=Interval.D1,
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-10"),
    )
    data_loader.fetch(req)

    assert krx_dl.call_count == 1
    assert bin_dl.call_count == 0


def test_invalid_symbol_does_not_create_cache_entry(mocker, writable_tmp_dir) -> None:
    from core.types.errors import InvalidSymbolError

    mocker.patch("core.data_loader.cache.cache_root", return_value=writable_tmp_dir)
    mocker.patch(
        "core.data_loader.binance_adapter.download",
        side_effect=InvalidSymbolError("nope"),
    )

    with pytest.raises(InvalidSymbolError):
        data_loader.fetch(_make_request(Market.CRYPTO))

    # No parquet files should have been written.
    assert not list(writable_tmp_dir.rglob("*.parquet"))
