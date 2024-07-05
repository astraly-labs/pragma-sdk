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
    original_pair = Pair(currencies["usdt"], currencies["usdc"])
    result = hop_handler.get_hop_pair(original_pair)

    assert result is not None
    assert result.base_currency == currencies["usdt"]
    assert result.quote_currency == currencies["usdt"]


def test_get_hop_pair_not_exists(currencies, hop_handler):
    original_pair = Pair(currencies["usdc"], currencies["btc"])
    result = hop_handler.get_hop_pair(original_pair)

    assert result is None


def test_get_hop_pair_chain(currencies, hop_handler):
    # Test first hop
    original_pair = Pair(currencies["eth"], currencies["usdc"])
    result = hop_handler.get_hop_pair(original_pair)

    assert result is not None
    assert result.base_currency == currencies["eth"]
    assert result.quote_currency == currencies["usdt"]

    # Test second hop
    second_hop = hop_handler.get_hop_pair(result)
    assert second_hop is not None
    assert second_hop.base_currency == currencies["eth"]
    assert second_hop.quote_currency == currencies["eth"]

    # Test third hop
    third_hop = hop_handler.get_hop_pair(second_hop)
    assert third_hop is not None
    assert third_hop.base_currency == currencies["eth"]
    assert third_hop.quote_currency == currencies["btc"]


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
