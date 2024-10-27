import pytest
import asyncio

from fakeredis import FakeStrictRedis

from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.redis_manager import (
    LpRedisManager,
)

MAINNET = "mainnet"
SEPOLIA = "sepolia"
POOL_ADDRESS = "0x068cfffac83830edbc3da6f13a9aa19266b3f5b677a57c58d7742087cf439fdd"
SAMPLE_RESERVES = (1000000, 2000000)
SAMPLE_TOTAL_SUPPLY = 500000


@pytest.fixture
def lp_redis_manager():
    redis_manager = LpRedisManager(host="fake", port="6379")
    fake_redis = FakeStrictRedis(server_type="redis")
    redis_manager.client = fake_redis
    return redis_manager


def test_store_pool_data(lp_redis_manager: LpRedisManager):
    result = lp_redis_manager.store_pool_data(
        MAINNET, POOL_ADDRESS, SAMPLE_RESERVES, SAMPLE_TOTAL_SUPPLY
    )
    assert result is True

    reserves = lp_redis_manager.get_latest_n_reserves(MAINNET, POOL_ADDRESS, 1)
    total_supply = lp_redis_manager.get_latest_n_total_supply(MAINNET, POOL_ADDRESS, 1)

    assert len(reserves) == 1
    assert reserves[0][0] == SAMPLE_RESERVES[0]
    assert reserves[0][1] == SAMPLE_RESERVES[1]
    assert len(total_supply) == 1
    assert total_supply[0] == SAMPLE_TOTAL_SUPPLY


def test_get_latest_n_reserves(lp_redis_manager: LpRedisManager):
    reserves_list = [
        (1000000, 2000000),
        (1100000, 2100000),
        (1200000, 2200000),
    ]

    for reserves in reserves_list:
        lp_redis_manager.store_pool_data(
            MAINNET, POOL_ADDRESS, reserves, SAMPLE_TOTAL_SUPPLY
        )

    latest_reserves = lp_redis_manager.get_latest_n_reserves(MAINNET, POOL_ADDRESS, 2)
    assert len(latest_reserves) == 2
    assert latest_reserves[0][0] == reserves_list[-1][0]
    assert latest_reserves[0][1] == reserves_list[-1][1]
    assert latest_reserves[1][0] == reserves_list[-2][0]
    assert latest_reserves[1][1] == reserves_list[-2][1]

    single_reserve = lp_redis_manager.get_latest_n_reserves(MAINNET, POOL_ADDRESS, 1)
    assert len(single_reserve) == 1
    assert single_reserve[0][0] == reserves_list[-1][0]
    assert single_reserve[0][1] == reserves_list[-1][1]

    non_existent = lp_redis_manager.get_latest_n_reserves(MAINNET, "0xnonexistent", 1)
    assert len(non_existent) == 0

    with pytest.raises(ValueError):
        lp_redis_manager.get_latest_n_reserves(MAINNET, POOL_ADDRESS, 0)


def test_get_latest_n_total_supply(lp_redis_manager: LpRedisManager):
    total_supply_list = [500000, 510000, 520000]

    for total_supply in total_supply_list:
        lp_redis_manager.store_pool_data(
            MAINNET, POOL_ADDRESS, SAMPLE_RESERVES, total_supply
        )

    latest_total_supply = lp_redis_manager.get_latest_n_total_supply(
        MAINNET, POOL_ADDRESS, 2
    )
    assert len(latest_total_supply) == 2
    assert latest_total_supply[0] == total_supply_list[-1]
    assert latest_total_supply[1] == total_supply_list[-2]

    single_total_supply = lp_redis_manager.get_latest_n_total_supply(
        MAINNET, POOL_ADDRESS, 1
    )
    assert len(single_total_supply) == 1
    assert single_total_supply[0] == total_supply_list[-1]

    non_existent = lp_redis_manager.get_latest_n_total_supply(
        MAINNET, "0xnonexistent", 1
    )
    assert len(non_existent) == 0


def test_lists_max_values(lp_redis_manager: LpRedisManager):
    for i in range(500):  # More than LISTS_MAX_VALUES
        lp_redis_manager.store_pool_data(MAINNET, POOL_ADDRESS, (i, i * 2), i)

    reserves = lp_redis_manager.get_latest_n_reserves(MAINNET, POOL_ADDRESS, 500)
    total_supply = lp_redis_manager.get_latest_n_total_supply(
        MAINNET, POOL_ADDRESS, 500
    )

    assert len(reserves) <= 480
    assert len(total_supply) <= 480

    assert reserves[0][0] == 499
    assert total_supply[0] == 499


def test_storage_across_networks(lp_redis_manager: LpRedisManager):
    mainnet_reserves = (1000000, 2000000)
    sepolia_reserves = (3000000, 4000000)

    lp_redis_manager.store_pool_data(MAINNET, POOL_ADDRESS, mainnet_reserves, 500000)
    lp_redis_manager.store_pool_data(SEPOLIA, POOL_ADDRESS, sepolia_reserves, 600000)

    mainnet_result = lp_redis_manager.get_latest_n_reserves(MAINNET, POOL_ADDRESS, 1)
    assert mainnet_result[0][0] == mainnet_reserves[0]
    assert mainnet_result[0][1] == mainnet_reserves[1]

    sepolia_result = lp_redis_manager.get_latest_n_reserves(SEPOLIA, POOL_ADDRESS, 1)
    assert sepolia_result[0][0] == sepolia_reserves[0]
    assert sepolia_result[0][1] == sepolia_reserves[1]


@pytest.mark.asyncio
async def test_ttl(lp_redis_manager: LpRedisManager):
    lp_redis_manager.time_to_live = 3

    result = lp_redis_manager.store_pool_data(
        MAINNET,
        POOL_ADDRESS,
        SAMPLE_RESERVES,
        SAMPLE_TOTAL_SUPPLY,
    )
    assert result is True

    reserves_key = f"{MAINNET}:{POOL_ADDRESS}:reserves"
    total_supply_key = f"{MAINNET}:{POOL_ADDRESS}:total_supply"

    assert lp_redis_manager.client.exists(reserves_key)
    assert lp_redis_manager.client.exists(total_supply_key)

    reserves_ttl = lp_redis_manager.client.ttl(reserves_key)
    total_supply_ttl = lp_redis_manager.client.ttl(total_supply_key)
    assert 0 < reserves_ttl <= 3
    assert 0 < total_supply_ttl <= 3

    result = lp_redis_manager.store_pool_data(
        MAINNET,
        POOL_ADDRESS,
        (2000000, 3000000),
        SAMPLE_TOTAL_SUPPLY,
    )
    assert result is True

    new_reserves_ttl = lp_redis_manager.client.ttl(reserves_key)
    new_total_supply_ttl = lp_redis_manager.client.ttl(total_supply_key)
    assert 0 < new_reserves_ttl <= 3
    assert 0 < new_total_supply_ttl <= 3

    # Wait for expiry
    await asyncio.sleep(lp_redis_manager.time_to_live + 1)

    assert not lp_redis_manager.client.exists(reserves_key)
    assert not lp_redis_manager.client.exists(total_supply_key)
