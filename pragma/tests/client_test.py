import time
from typing import Tuple
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from starknet_py.cairo.felt import decode_shortstring
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.hash.storage import get_storage_var_address
from starknet_py.net.account.base_account import BaseAccount

from pragma.core.client import PragmaClient
from pragma.core.types import ContractAddresses
from pragma.core.utils import str_to_felt
from pragma.tests.constants import (
    CURRENCIES,
    DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
    DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
    MOCK_COMPILED_DIR,
    PAIRS,
    U128_MAX,
    U256_MAX,
)
from pragma.tests.utils import read_contract


@pytest_asyncio.fixture(scope="package")
async def declare_deploy_oracle(
    account: BaseAccount,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract_registry = read_contract(
        "pragma_PublisherRegistry.sierra.json", directory=None
    )
    compiled_contract_registry_casm = read_contract(
        "pragma_PublisherRegistry.casm.json", directory=None
    )

    compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Oracle.casm.json", directory=None)

    # Declare Publisher Registry
    declare_result_registry = await Contract.declare(
        account=account,
        compiled_contract=compiled_contract_registry,
        compiled_contract_casm=compiled_contract_registry_casm,
        auto_estimate=True,
    )
    await declare_result_registry.wait_for_acceptance()

    # Deploy Publisher Registry
    deploy_result_registry = await declare_result_registry.deploy(
        constructor_args=[account.address], auto_estimate=True
    )
    await deploy_result_registry.wait_for_acceptance()

    # Declare Oracle
    declare_result = await Contract.declare(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Deploy Oracle
    currencies = [currency.to_dict() for currency in CURRENCIES]
    pairs = [pair.to_dict() for pair in PAIRS]

    print(currencies, pairs)

    deploy_result = await declare_result.deploy(
        constructor_args=[
            account.address,
            deploy_result_registry.deployed_contract.address,
            currencies,
            pairs,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_result_registry


@pytest_asyncio.fixture(scope="package", name="contracts")
# pylint: disable=redefined-outer-name
async def oracle_contract(declare_deploy_oracle) -> (Contract, Contract):
    _, deploy_result, deploy_result_registry = declare_deploy_oracle
    return (deploy_result.deployed_contract, deploy_result_registry.deployed_contract)


@pytest_asyncio.fixture(scope="package", name="pragma_client")
# pylint: disable=redefined-outer-name
async def pragma_client(
    contracts: (Contract, Contract),
    account: BaseAccount,
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    oracle, registry = contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    print(account.address, address)

    return PragmaClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(registry.address, oracle.address),
        port=port,
    )


@pytest.mark.asyncio
async def test_deploy_contract(contracts):
    oracle, registry = contracts
    assert isinstance(oracle, Contract)
    assert isinstance(registry, Contract)


@pytest.mark.asyncio
async def test_client_setup(
    contracts: (Contract, Contract), pragma_client: PragmaClient, account: BaseAccount
):
    oracle, registry = contracts
    assert pragma_client.account_address() == account.address

    account_balance = await account.get_balance()
    assert await pragma_client.get_balance(account.address) == account_balance

    assert pragma_client.oracle is not None
    assert pragma_client.publisher_registry is not None


@pytest.mark.asyncio
async def test_client_publisher_mixin(pragma_client: PragmaClient, contracts):
    oracle, registry = contracts
    publishers = await pragma_client.get_all_publishers()
    assert publishers == []

    PUBLISHER_NAME = "PUBLISHER_1"
    PUBLISHER_ADDRESS = 123

    await pragma_client.add_publisher(PUBLISHER_NAME, PUBLISHER_ADDRESS)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt(PUBLISHER_NAME)]

    publisher_address = await pragma_client.get_publisher_address(PUBLISHER_NAME)
    assert publisher_address == PUBLISHER_ADDRESS

    SOURCE_1 = "SOURCE_1"

    await pragma_client.add_source_for_publisher(PUBLISHER_NAME, SOURCE_1)

    sources = await pragma_client.get_publisher_sources(PUBLISHER_NAME)
    assert sources == [str_to_felt(SOURCE_1)]

    SOURCE_2 = "SOURCE_2"
    SOURCE_3 = "SOURCE_3"

    await pragma_client.add_sources_for_publisher(PUBLISHER_NAME, [SOURCE_2, SOURCE_3])

    sources = await pragma_client.get_publisher_sources(PUBLISHER_NAME)
    assert sources == [str_to_felt(source) for source in (SOURCE_1, SOURCE_2, SOURCE_3)]


@pytest.mark.asyncio
async def test_client_oracle_mixin(pragma_client: PragmaClient, contracts):
    oracle, registry = contracts

    # Add PRAGMA as Publisher
    PUBLISHER_NAME = "PRAGMA"
    PUBLISHER_ADDRESS = pragma_client.account_address()

    await pragma_client.add_publisher(PUBLISHER_NAME, PUBLISHER_ADDRESS)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(PUBLISHER_NAME)]

    # Add PRAGMA as Source for PRAGMA Publisher
    SOURCE_1 = "PRAGMA"
    await pragma_client.add_source_for_publisher(PUBLISHER_NAME, SOURCE_1)

    # Publish SPOT Entry
    BTC_PAIR = str_to_felt("BTC/USD")
    timestamp = int(time.time())
    await pragma_client.publish_spot_entry(
        BTC_PAIR, 100, timestamp, SOURCE_1, PUBLISHER_NAME
    )

    # Get SPOT
    res = await pragma_client.get_spot(BTC_PAIR)
    assert res.price == 100
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp
    assert res.decimals == 8


# @pytest.mark.asyncio
# async def test_client_publisher_mixin_update_address(pragma_client: PragmaClient, contracts):
#     oracle, registry = contracts

#     PUBLISHER_ADDRESS_NEW = 456
#     await pragma_client.update_publisher_address(PUBLISHER_NAME, PUBLISHER_ADDRESS_NEW)

#     publisher_address = await pragma_client.get_publisher_address(PUBLISHER_NAME)
#     assert publisher_address == PUBLISHER_ADDRESS_NEW
