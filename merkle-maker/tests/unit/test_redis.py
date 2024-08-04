import pytest

from starknet_py.hash.hash_method import HashMethod
from starknet_py.utils.merkle_tree import MerkleTree
from fakeredis import FakeStrictRedis

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import (
    OptionData,
    LatestData,
    DeribitOptionResponse,
    CurrenciesOptions,
)

from merkle_maker.redis import RedisManager

MAINNET = "mainnet"
SEPOLIA = "sepolia"

CURRENT_BLOCK = 69420


@pytest.fixture
def redis_manager():
    redis_manager = RedisManager(host="fake", port="6379")
    fake_redis = FakeStrictRedis()
    redis_manager.client = fake_redis
    return redis_manager


@pytest.fixture
def sample_deribit_response():
    return DeribitOptionResponse.from_dict(
        {
            "mid_price": 0.001,
            "estimated_delivery_price": 68813.31,
            "volume_usd": 0,
            "quote_currency": "BTC",
            "creation_timestamp": 1722095703700,
            "base_currency": "BTC",
            "underlying_index": "BTC-27DEC24",
            "underlying_price": 72298.65,
            "mark_iv": 85.14,
            "volume": 0,
            "interest_rate": 0,
            "price_change": None,
            "open_interest": 167.2,
            "ask_price": 0.0014,
            "bid_price": 0.0006,
            "instrument_name": "BTC-27DEC24-20000-P",
            "mark_price": 0.00093025,
            "last": 0.001,
            "low": None,
            "high": None,
        }
    )


@pytest.fixture
def sample_option_data(sample_deribit_response: DeribitOptionResponse) -> OptionData:
    btc_usd = Pair.from_tickers("BTC", "USD")
    decimals = btc_usd.base_currency.decimals
    return OptionData.from_deribit_response(sample_deribit_response, decimals)


@pytest.fixture
def sample_options(sample_option_data: OptionData) -> CurrenciesOptions:
    return {"BTC": [sample_option_data]}


@pytest.fixture
def sample_merkle_tree(sample_option_data: OptionData) -> MerkleTree:
    return MerkleTree(
        leaves=[sample_option_data.get_pedersen_hash()], hash_method=HashMethod.PEDERSEN
    )


def test_store_block_data(
    redis_manager: RedisManager, sample_merkle_tree: MerkleTree, sample_options: CurrenciesOptions
):
    latest_data = LatestData(merkle_tree=sample_merkle_tree, options=sample_options)
    assert redis_manager.store_block_data(MAINNET, CURRENT_BLOCK, latest_data)
    assert not redis_manager.store_block_data(MAINNET, CURRENT_BLOCK, None)


def test_get_option(redis_manager: RedisManager, sample_options: CurrenciesOptions):
    redis_manager._store_options(MAINNET, CURRENT_BLOCK, sample_options)
    instrument = "BTC-27DEC24-20000-P"

    result = redis_manager.get_option(MAINNET, CURRENT_BLOCK, instrument)
    assert result is not None
    assert isinstance(result, OptionData)
    assert result.instrument_name == instrument
    assert result.mark_price == sample_options["BTC"][0].mark_price
    assert result.current_timestamp == sample_options["BTC"][0].current_timestamp
    assert result.base_currency == sample_options["BTC"][0].base_currency

    redis_manager.client.delete(f"{MAINNET}/{CURRENT_BLOCK}/options/BTC-27DEC24-20000-P")
    assert redis_manager.get_option(MAINNET, CURRENT_BLOCK, instrument) is None


def test_get_all_options(redis_manager: RedisManager, sample_options: CurrenciesOptions):
    redis_manager._store_options(MAINNET, CURRENT_BLOCK, sample_options)

    result = redis_manager.get_all_options(MAINNET, CURRENT_BLOCK)
    assert result is not None
    assert "BTC" in result
    assert len(result["BTC"]) == 1
    assert isinstance(result["BTC"][0], OptionData)
    assert result["BTC"][0].instrument_name == "BTC-27DEC24-20000-P"

    pattern = f"{MAINNET}/{CURRENT_BLOCK}/options/*"
    keys_to_delete = redis_manager.client.keys(pattern)
    if keys_to_delete:
        redis_manager.client.delete(*keys_to_delete)

    assert redis_manager.get_option(MAINNET, CURRENT_BLOCK, "BTC-27DEC24-20000-P") is None
    assert redis_manager.get_all_options(MAINNET, CURRENT_BLOCK) is None


def test_get_merkle_tree(redis_manager: RedisManager, sample_merkle_tree: MerkleTree):
    redis_manager._store_merkle_tree(SEPOLIA, CURRENT_BLOCK, sample_merkle_tree)

    out = redis_manager.get_merkle_tree(SEPOLIA, CURRENT_BLOCK)
    assert out is not None
    assert len(out.leaves) == 1
    assert out.hash_method == HashMethod.PEDERSEN

    redis_manager.client.delete(f"{SEPOLIA}/{CURRENT_BLOCK}/merkle_tree")
    assert redis_manager.get_merkle_tree(SEPOLIA, CURRENT_BLOCK) is None


def test_store_merkle_tree(redis_manager: RedisManager, sample_merkle_tree: MerkleTree):
    assert redis_manager._store_merkle_tree(SEPOLIA, CURRENT_BLOCK, sample_merkle_tree)


def test_store_options(redis_manager: RedisManager, sample_options: CurrenciesOptions):
    assert redis_manager._store_options(MAINNET, CURRENT_BLOCK, sample_options)
