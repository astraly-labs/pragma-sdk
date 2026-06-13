import pytest
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler


@pytest.fixture
def currencies():
    return {
        "usdt": Currency.from_asset_config(AssetConfig.from_ticker("USDT")),
        "usdc": Currency.from_asset_config(AssetConfig.from_ticker("USDC")),
        "eth": Currency.from_asset_config(AssetConfig.from_ticker("ETH")),
        "btc": Currency.from_asset_config(AssetConfig.from_ticker("BTC")),
    }


@pytest.fixture
def hop_handler():
    return HopHandler(hopped_currencies={"USDC": "USDT", "USDT": "ETH", "ETH": "BTC"})


def test_get_hop_pair_exists(currencies, hop_handler):
    # BTC/USDC -> BTC/USDT (USDC hops to USDT, base stays BTC)
    original_pair = Pair(currencies["btc"], currencies["usdc"])
    result = hop_handler.get_hop_pair(original_pair)

    assert result is not None
    assert result.base_currency == currencies["btc"]
    assert result.quote_currency == currencies["usdt"]


def test_get_hop_pair_not_exists(currencies, hop_handler):
    original_pair = Pair(currencies["usdc"], currencies["btc"])
    result = hop_handler.get_hop_pair(original_pair)

    assert result is None


def test_get_hop_pair_chain(currencies, hop_handler):
    # Test first hop: ETH/USDC -> ETH/USDT
    original_pair = Pair(currencies["eth"], currencies["usdc"])
    result = hop_handler.get_hop_pair(original_pair)

    assert result is not None
    assert result.base_currency == currencies["eth"]
    assert result.quote_currency == currencies["usdt"]

    # Second hop would be ETH/USDT -> ETH/ETH (USDT hops to ETH), which is a
    # degenerate X/X pair: the handler now returns None instead.
    second_hop = hop_handler.get_hop_pair(result)
    assert second_hop is None


def test_get_hop_pair_skips_degenerate(currencies):
    # Real-world case: USDT/USD with a USD->USDT hop would become USDT/USDT.
    # We must NOT hop, so the fetcher can query USDT/USD directly.
    handler = HopHandler(hopped_currencies={"USD": "USDT"})
    usd = Currency.from_asset_config(AssetConfig.from_ticker("USD"))
    pair = Pair(currencies["usdt"], usd)
    assert handler.get_hop_pair(pair) is None

    # A non-degenerate pair with the same handler still hops: BTC/USD -> BTC/USDT
    btc_usd = Pair(currencies["btc"], usd)
    hopped = handler.get_hop_pair(btc_usd)
    assert hopped is not None
    assert hopped.base_currency == currencies["btc"]
    assert hopped.quote_currency == currencies["usdt"]


def test_empty_hop_handler(currencies):
    empty_handler = HopHandler()
    pair = Pair(currencies["usdt"], currencies["usdc"])
    result = empty_handler.get_hop_pair(pair)

    assert result is None


def test_get_hop_pair_same_currency(currencies):
    handler = HopHandler(hopped_currencies={"USDT": "USDT"})
    pair = Pair(currencies["eth"], currencies["usdt"])
    result = handler.get_hop_pair(pair)

    assert result is not None
    assert result.base_currency == currencies["eth"]
    assert result.quote_currency == currencies["usdt"]
