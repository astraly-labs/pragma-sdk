import pytest

from starknet_py.hash.hash_method import HashMethod
from starknet_py.utils.merkle_tree import MerkleTree
from fakeredis import FakeStrictRedis

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import (
    OptionData,
    LatestData,
    DeribitOptionResponse,
    CurrenciesOptions,
)

from merkle_maker.redis import RedisManager

MAINNET = "mainnet"
SEPOLIA = "sepolia"


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
    return OptionData.from_deribit_response(sample_deribit_response)


@pytest.fixture
def sample_options(sample_option_data: OptionData) -> CurrenciesOptions:
    return {"BTC": [sample_option_data]}


@pytest.fixture
def sample_merkle_tree(sample_option_data: OptionData) -> MerkleTree:
    return MerkleTree(leaves=[hash(sample_option_data)], hash_method=HashMethod.PEDERSEN)


def test_store_latest_data(
    redis_manager: RedisManager, sample_merkle_tree: MerkleTree, sample_options: CurrenciesOptions
):
    latest_data = LatestData(merkle_tree=sample_merkle_tree, options=sample_options)
    assert redis_manager.store_latest_data(MAINNET, latest_data)
    assert not redis_manager.store_latest_data(MAINNET, None)


def test_get_options(redis_manager: RedisManager, sample_options: CurrenciesOptions):
    redis_manager._store_latest_options(MAINNET, sample_options)

    result = redis_manager.get_options(MAINNET)
    assert result is not None
    assert "BTC" in result
    assert len(result["BTC"]) == 1
    assert isinstance(result["BTC"][0], OptionData)
    assert result["BTC"][0].instrument_name == "BTC-27DEC24-20000-P"

    redis_manager.client.delete(f"{MAINNET}/last_options")
    assert redis_manager.get_options(MAINNET) is None


def test_get_merkle_tree(redis_manager: RedisManager, sample_merkle_tree: MerkleTree):
    redis_manager._store_latest_merkle_tree(SEPOLIA, sample_merkle_tree)

    out = redis_manager.get_merkle_tree(SEPOLIA)
    assert out is not None
    assert len(out.leaves) == 1
    assert out.hash_method == HashMethod.PEDERSEN

    redis_manager.client.delete(f"{SEPOLIA}/last_merkle_tree")
    assert redis_manager.get_merkle_tree(SEPOLIA) is None


def test_store_latest_merkle_tree(redis_manager: RedisManager, sample_merkle_tree: MerkleTree):
    assert redis_manager._store_latest_merkle_tree(SEPOLIA, sample_merkle_tree)


def test_store_latest_options(redis_manager: RedisManager, sample_options: CurrenciesOptions):
    assert redis_manager._store_latest_options(MAINNET, sample_options)
