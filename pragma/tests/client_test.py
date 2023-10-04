import time
from typing import Tuple
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.base_account import BaseAccount
from starknet_py.net.client_errors import ClientError

from pragma.core.client import PragmaClient
from pragma.core.entry import FutureEntry, SpotEntry
from pragma.core.types import ContractAddresses, DataType, DataTypes
from pragma.core.utils import str_to_felt
from pragma.tests.constants import CURRENCIES, PAIRS
from pragma.tests.utils import read_contract

PUBLISHER_NAME = "PRAGMA"

ETH_PAIR = str_to_felt("ETH/USD")
BTC_PAIR = str_to_felt("BTC/USD")

SOURCE_1 = "PRAGMA_1"
SOURCE_2 = "PRAGMA_2"
SOURCE_3 = "SOURCE_3"


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
async def pragma_client(
    contracts: (Contract, Contract),
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    oracle, registry = contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

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
# pylint: disable=redefined-outer-name
async def test_client_setup(pragma_client: PragmaClient, account: BaseAccount):
    assert pragma_client.account_address() == account.address

    account_balance = await account.get_balance()
    assert await pragma_client.get_balance(account.address) == account_balance

    assert pragma_client.oracle is not None
    assert pragma_client.publisher_registry is not None


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_client_publisher_mixin(pragma_client: PragmaClient):
    publishers = await pragma_client.get_all_publishers()
    assert publishers == []

    publisher_name = "PUBLISHER_1"
    expected_publisher_address = 123

    await pragma_client.add_publisher(publisher_name, expected_publisher_address)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt(publisher_name)]

    publisher_address = await pragma_client.get_publisher_address(publisher_name)
    assert expected_publisher_address == publisher_address

    await pragma_client.add_source_for_publisher(publisher_name, SOURCE_1)

    sources = await pragma_client.get_publisher_sources(publisher_name)
    assert sources == [str_to_felt(SOURCE_1)]

    await pragma_client.add_sources_for_publisher(publisher_name, [SOURCE_2, SOURCE_3])

    sources = await pragma_client.get_publisher_sources(publisher_name)
    assert sources == [str_to_felt(source) for source in (SOURCE_1, SOURCE_2, SOURCE_3)]


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_client_oracle_mixin_spot(pragma_client: PragmaClient):
    # Add PRAGMA as Publisher
    publisher_name = "PRAGMA"
    publisher_address = pragma_client.account_address()

    await pragma_client.add_publisher(publisher_name, publisher_address)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(publisher_name)]

    # Add PRAGMA as Source for PRAGMA Publisher
    await pragma_client.add_source_for_publisher(publisher_name, SOURCE_1)

    # Publish SPOT Entry
    timestamp = int(time.time())
    await pragma_client.publish_spot_entry(
        BTC_PAIR, 100, timestamp, SOURCE_1, publisher_name, volume=int(200 * 100 * 1e8)
    )

    entries = await pragma_client.get_spot_entries(BTC_PAIR, sources=[])
    assert entries == [SpotEntry(BTC_PAIR, 100, timestamp, SOURCE_1, 0, volume=200)]

    # Get SPOT
    res = await pragma_client.get_spot(BTC_PAIR)
    assert res.price == 100
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp
    assert res.decimals == 8

    # Get Decimals
    decimals = await pragma_client.get_decimals(
        DataType(DataTypes.SPOT, BTC_PAIR, None)
    )
    assert decimals == 8

    # Publish many SPOT entries
    spot_entry_1 = SpotEntry(
        ETH_PAIR, 100, timestamp, SOURCE_1, publisher_name, volume=10
    )
    spot_entry_2 = SpotEntry(
        ETH_PAIR, 200, timestamp + 10, SOURCE_1, publisher_name, volume=20
    )

    await pragma_client.publish_many([spot_entry_1, spot_entry_2])

    # Fails for UNKNOWN source
    unknown_source = "UNKNOWN"
    try:
        await pragma_client.get_spot_entries(
            ETH_PAIR, sources=[str_to_felt(unknown_source)]
        )
    except ClientError as err:
        err_msg = "Execution was reverted; failure reason: [0x4e6f206461746120656e74727920666f756e64]"
        if not err_msg in err.message:
            raise err

    # Returns correct entries
    entries = await pragma_client.get_spot_entries(ETH_PAIR, sources=[])

    spot_entry_2.set_publisher(0)
    assert entries == [spot_entry_2]

    # Return correct price aggregated
    res = await pragma_client.get_spot(ETH_PAIR)
    assert res.price == 200
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp + 10
    assert res.decimals == 8

    # Add new source and check aggregation
    await pragma_client.add_source_for_publisher(publisher_name, SOURCE_2)
    spot_entry_1 = SpotEntry(
        ETH_PAIR, 100, timestamp + 20, SOURCE_1, publisher_name, volume=10
    )
    spot_entry_2 = SpotEntry(
        ETH_PAIR, 200, timestamp + 30, SOURCE_2, publisher_name, volume=20
    )

    await pragma_client.publish_many([spot_entry_1, spot_entry_2])

    res = await pragma_client.get_spot(ETH_PAIR)
    assert res.price == 150
    assert res.num_sources_aggregated == 2
    assert res.last_updated_timestamp == timestamp + 30
    assert res.decimals == 8


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_client_oracle_mixin_future(pragma_client: PragmaClient):
    # Checks
    publisher_name = "PRAGMA"
    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt("PUBLISHER_1"), str_to_felt(publisher_name)]

    timestamp = int(time.time())
    expiry_timestamp = timestamp + 1000
    future_entry_1 = FutureEntry(
        BTC_PAIR,
        1000,
        timestamp,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=10000,
    )
    future_entry_2 = FutureEntry(
        BTC_PAIR,
        2000,
        timestamp + 100,
        SOURCE_1,
        publisher_name,
        expiry_timestamp,
        volume=20000,
    )

    await pragma_client.publish_many([future_entry_1, future_entry_2])

    # Check entries
    entries = await pragma_client.get_future_entries(
        BTC_PAIR, expiry_timestamp, sources=[]
    )
    future_entry_2.base.publisher = 0
    assert entries == [future_entry_2]

    # Get FUTURE
    res = await pragma_client.get_future(BTC_PAIR, expiry_timestamp)
    assert res.price == 2000
    assert res.num_sources_aggregated == 1
    assert res.last_updated_timestamp == timestamp + 100
    assert res.decimals == 8
    assert res.expiration_timestamp == expiry_timestamp

    # Add new source and check aggregation
    future_entry_1 = FutureEntry(
        ETH_PAIR, 100, timestamp, SOURCE_1, publisher_name, expiry_timestamp, volume=10
    )
    future_entry_2 = FutureEntry(
        ETH_PAIR,
        200,
        timestamp + 10,
        SOURCE_2,
        publisher_name,
        expiry_timestamp,
        volume=20,
    )

    await pragma_client.publish_many([future_entry_1, future_entry_2])

    res = await pragma_client.get_future(ETH_PAIR, expiry_timestamp)
    assert res.price == 150
    assert res.num_sources_aggregated == 2
    assert res.last_updated_timestamp == timestamp + 10
    assert res.decimals == 8


def test_client_with_http_network():
    client_with_chain_name = PragmaClient(
        network="http://test.rpc/rpc", chain_name="testnet"
    )
    assert client_with_chain_name.network == "testnet"

    client_with_chain_name_only = PragmaClient(chain_name="devnet")
    # default value of network is testnet
    assert client_with_chain_name_only.network == "testnet"

    with pytest.raises(Exception) as exception:
        _ = PragmaClient(network="http://test.rpc/rpc")
        assert "`chain_name` is not provided" in str(exception)
