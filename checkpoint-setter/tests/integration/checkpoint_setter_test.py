import asyncio
import pytest
import logging

from typing import List
from urllib.parse import urlparse
from starknet_py.contract import Contract

from pragma_sdk.common.types.types import DataTypes, AggregationMode
from pragma_sdk.common.types.entry import SpotEntry, FutureEntry
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_utils.logger import setup_logging
from pragma_sdk.common.utils import str_to_felt

from checkpoint_setter.main import main
from checkpoint_setter.configs.pairs_config import PairsConfig

logger = logging.getLogger(__name__)

PUBLISHER_NAME = "PRAGMA"


def spawn_main_in_parallel_thread(
    network,
    spot_pairs: List[str],
    future_pairs: List[str],
    oracle_address: int,
    admin_address: int,
    private_key: str,
    check_requests_interval: float = 1 / 60,  # 1 second, check_requests_interval is in minutes
) -> asyncio.Task:
    """
    Spawns the main function in a parallel thread and return the task.
    The task can later be cancelled using the .cancel function.
    """
    pairs_config = PairsConfig(spot=spot_pairs, future=future_pairs)
    port = urlparse(network).port
    main_task = asyncio.create_task(
        main(
            pairs_config=pairs_config,
            network="devnet",
            rpc_url=f"http://localhost:{port}",
            oracle_address=hex(oracle_address),
            admin_address=hex(admin_address),
            private_key=private_key,
            set_checkpoint_interval=check_requests_interval,
        )
    )
    return main_task


@pytest.mark.asyncio
async def test_checkpoint_setter_only_spot(
    pragma_client: PragmaOnChainClient,
    deploy_oracle_contracts: (Contract, Contract),
    address_and_private_key,
    network,
):
    setup_logging(logger, "DEBUG")

    _, private_key = address_and_private_key
    (oracle, publisher_registry) = deploy_oracle_contracts
    caller_address = pragma_client.account_address

    latest_checkpoint = await pragma_client.get_latest_checkpoint(
        str_to_felt("BTC/USD"), DataTypes.SPOT, AggregationMode.MEDIAN
    )
    assert latest_checkpoint.timestamp == 0

    # Register publisher
    tx = await pragma_client.add_publisher(PUBLISHER_NAME, caller_address)
    await tx.wait_for_acceptance()
    tx = await pragma_client.add_source_for_publisher(PUBLISHER_NAME, "BINANCE")
    await tx.wait_for_acceptance()

    # Publish one entry to BTC/USD
    btc_spot_entry = SpotEntry(
        pair_id="BTC/USD",
        price=4242424242,
        timestamp=4242424242,
        source="BINANCE",
        publisher=PUBLISHER_NAME,
    )
    txs = await pragma_client.publish_many([btc_spot_entry])
    await txs[-1].wait_for_acceptance()
    logger.info("💚 Published one entry for BTC/USD!")

    main_task = spawn_main_in_parallel_thread(
        spot_pairs=["BTC/USD"],
        future_pairs=[],
        network=network,
        oracle_address=oracle.address,
        admin_address=caller_address,
        private_key=private_key,
    )

    await asyncio.sleep(2)

    latest_checkpoint = await pragma_client.get_latest_checkpoint(
        str_to_felt("BTC/USD"), DataTypes.SPOT, AggregationMode.MEDIAN
    )
    assert latest_checkpoint.timestamp > 0
    assert latest_checkpoint.value == 4242424242
    assert latest_checkpoint.num_sources_aggregated == 1

    main_task.cancel()


@pytest.mark.asyncio
async def test_checkpoint_setter_only_future(
    pragma_client: PragmaOnChainClient,
    deploy_oracle_contracts: (Contract, Contract),
    address_and_private_key,
    network,
):
    setup_logging(logger, "DEBUG")

    _, private_key = address_and_private_key
    (oracle, publisher_registry) = deploy_oracle_contracts
    caller_address = pragma_client.account_address

    latest_checkpoint = await pragma_client.get_latest_checkpoint(
        str_to_felt("BTC/USD"), DataTypes.SPOT, AggregationMode.MEDIAN
    )
    assert latest_checkpoint.timestamp == 0

    # Register publisher
    tx = await pragma_client.add_publisher(PUBLISHER_NAME, caller_address)
    await tx.wait_for_acceptance()
    tx = await pragma_client.add_source_for_publisher(PUBLISHER_NAME, "BINANCE")
    await tx.wait_for_acceptance()

    # Publish one entry to BTC/USD
    btc_spot_entry = FutureEntry(
        pair_id="BTC/USD",
        price=4242424242,
        timestamp=4242424242,
        source="BINANCE",
        publisher=PUBLISHER_NAME,
        expiry_timestamp=0,
    )
    txs = await pragma_client.publish_many([btc_spot_entry])
    await txs[-1].wait_for_acceptance()
    logger.info("💚 Published one entry for BTC/USD!")

    main_task = spawn_main_in_parallel_thread(
        spot_pairs=[],
        future_pairs=["BTC/USD"],
        network=network,
        oracle_address=oracle.address,
        admin_address=caller_address,
        private_key=private_key,
    )

    await asyncio.sleep(2)

    latest_checkpoint = await pragma_client.get_latest_checkpoint(
        str_to_felt("BTC/USD"), DataTypes.FUTURE, AggregationMode.MEDIAN, expiration_timestamp=0
    )
    logger.info(latest_checkpoint)
    assert latest_checkpoint.timestamp > 0
    assert latest_checkpoint.value == 4242424242
    assert latest_checkpoint.num_sources_aggregated == 1

    main_task.cancel()
