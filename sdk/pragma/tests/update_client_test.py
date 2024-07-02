import logging
import os
from typing import Tuple
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult
from starknet_py.net.client_errors import ClientError

from pragma.onchain.client import PragmaOnChainClient
from pragma.onchain.types import ContractAddresses
from pragma.common.utils import str_to_felt
from pragma.tests.utils import get_deployments, read_contract


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_FEE = 3700000000000000
PUBLISHER_NAME = "PRAGMA"

ETH_PAIR = str_to_felt("ETH/USD")
BTC_PAIR = str_to_felt("BTC/USD")

SOURCE_1 = "PRAGMA_1"
SOURCE_2 = "PRAGMA_2"
SOURCE_3 = "SOURCE_3"


@pytest_asyncio.fixture(scope="package", name="pragma_fork_client")
async def pragma_fork_client(
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaOnChainClient:
    # TODO(#000): refactor this
    fork_network = os.getenv("NETWORK_FORK")
    deployments = get_deployments(
        fork_network if fork_network != "devnet" else "mainnet"
    )
    oracle = deployments["pragma_Oracle"]
    registry = deployments["pragma_PublisherRegistry"]
    address, private_key = address_and_private_key
    port = urlparse(network).port
    return PragmaOnChainClient(
        network="fork_devnet",
        chain_name="mainnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            registry["address"], oracle["address"]
        ),
        port=port,
    )


@pytest_asyncio.fixture(scope="package")
async def declare_oracle(pragma_fork_client: PragmaOnChainClient) -> DeclareResult:
    try:
        compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
        compiled_contract_casm = read_contract(
            "pragma_Oracle.casm.json", directory=None
        )
        # Declare Oracle
        declare_result = await Contract.declare_v2(
            account=pragma_fork_client.account,
            compiled_contract=compiled_contract,
            compiled_contract_casm=compiled_contract_casm,
            auto_estimate=True,
        )
        await declare_result.wait_for_acceptance()
        return declare_result

    except ClientError as err:
        if "is already declared" in err.message:
            logger.info("Contract already declared with this class hash")
        else:
            logger.info("An error occured during the declaration: %s", err)
            raise err
        return None


@pytest.mark.asyncio
async def test_update_oracle(
    pragma_fork_client: PragmaOnChainClient, declare_oracle: DeclareResult
):
    # TODO(#000): refactor this
    fork_network = os.getenv("NETWORK_FORK")
    deployments = get_deployments(
        fork_network if fork_network != "devnet" else "sepolia"
    )

    if declare_oracle is None:
        pytest.skip("oracle_declare failed. Skipping this test...")

    # Retrieve old state

    publishers = await pragma_fork_client.get_all_publishers()
    initial_prices = await retrieve_spot_prices(pragma_fork_client, PRAGMA_ALL_ASSETS)
    oracle_admin = await pragma_fork_client.get_admin_address()
    assert oracle_admin == pragma_fork_client.account_address()

    # Determine new implementation hash
    declare_result = declare_oracle
    logger.info("Contract declared with hash: %s", declare_result.class_hash)

    # Update oracle
    update_invoke = await pragma_fork_client.update_oracle(
        declare_result.class_hash, MAX_FEE
    )
    update_invoke.wait_for_acceptance()
    logger.info("Contract upgraded with tx %s", hex(update_invoke.hash))

    # Check that the class hash was updated
    class_hash = await pragma_fork_client.full_node_client.get_class_hash_at(
        deployments["pragma_Oracle"]["address"]
    )
    # assert class_hash['result'] == declare_result.class_hash
    assert class_hash == declare_result.class_hash
    # Retrieve new state
    new_publishers = await pragma_fork_client.get_all_publishers()
    post_treatment_prices = await retrieve_spot_prices(
        pragma_fork_client, PRAGMA_ALL_ASSETS
    )

    # Check that state is the same
    assert publishers == new_publishers
    assert initial_prices == post_treatment_prices


async def retrieve_spot_prices(client: PragmaOnChainClient, assets):
    prices = {}
    for asset in assets:
        if asset["type"] == "SPOT":
            pair = asset["pair"]
            price = await client.get_spot(str_to_felt(pair[0] + "/" + pair[1]))
            prices[pair] = price
    return prices
