import time
import pytest
import pytest_asyncio

from typing import Tuple
from urllib.parse import urlparse

from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import OptionData
from pragma_sdk.common.types.entry import GenericEntry
from pragma_sdk.common.utils import felt_to_str

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types import ContractAddresses, Network
from pragma_sdk.onchain.constants import DERIBIT_MERKLE_FEED_KEY

from tests.integration.constants import CURRENCIES, USD_PAIRS
from tests.integration.utils import read_contract, wait_for_acceptance


PUBLISHER_NAME = "PRAGMA"

SOURCE_1 = "PRAGMA_1"


@pytest_asyncio.fixture(scope="module")
async def declare_deploy_oracle(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract_registry = read_contract(
        "pragma_PublisherRegistry.sierra.json", directory=None
    )
    compiled_contract_registry_casm = read_contract(
        "pragma_PublisherRegistry.casm.json", directory=None
    )

    compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Oracle.casm.json", directory=None)

    compiled_contract_summary = read_contract(
        "pragma_SummaryStats.sierra.json", directory=None
    )
    compiled_contract_summary_casm = read_contract(
        "pragma_SummaryStats.casm.json", directory=None
    )

    # Declare Publisher Registry
    declare_result_registry = await Contract.declare_v3(
        account=account,
        compiled_contract=compiled_contract_registry,
        compiled_contract_casm=compiled_contract_registry_casm,
        auto_estimate=True,
    )
    await declare_result_registry.wait_for_acceptance()

    # Deploy Publisher Registry
    deploy_result_registry = await declare_result_registry.deploy_v1(
        constructor_args=[account.address], auto_estimate=True
    )
    await deploy_result_registry.wait_for_acceptance()

    # Declare Oracle
    declare_result = await Contract.declare_v3(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Deploy Oracle
    all_currencies = CURRENCIES[:40]
    all_pairs = USD_PAIRS[:20]

    currencies = [currency.to_dict() for currency in all_currencies]
    pairs = [pair.to_dict() for pair in all_pairs]

    deploy_result = await declare_result.deploy_v1(
        constructor_args=[
            account.address,
            deploy_result_registry.deployed_contract.address,
            currencies,
            pairs,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    # Declare Summary Stats
    declare_result_summary = await Contract.declare_v3(
        account=account,
        compiled_contract=compiled_contract_summary,
        compiled_contract_casm=compiled_contract_summary_casm,
        auto_estimate=True,
    )
    await declare_result_summary.wait_for_acceptance()

    # Deploy Summary Stats
    deploy_result_summary = await declare_result_summary.deploy_v1(
        constructor_args=[deploy_result.deployed_contract.address],
        auto_estimate=True,
    )
    await deploy_result_summary.wait_for_acceptance()

    return declare_result, deploy_result, deploy_result_registry, deploy_result_summary


@pytest_asyncio.fixture(scope="module", name="contracts")
async def oracle_contract(declare_deploy_oracle) -> Tuple[Contract, Contract]:
    _, deploy_result, deploy_result_registry, deploy_result_summary = (
        declare_deploy_oracle
    )
    return (
        deploy_result.deployed_contract,
        deploy_result_registry.deployed_contract,
        deploy_result_summary.deployed_contract,
    )


@pytest_asyncio.fixture(scope="module", name="pragma_client")
async def pragma_client(
    contracts: Tuple[Contract, Contract],
    network: Network,
    address_and_private_key: Tuple[str, str],
) -> PragmaOnChainClient:
    oracle, registry, summary = contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    return PragmaOnChainClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=registry.address,
            oracle_proxy_addresss=oracle.address,
            summary_stats_address=summary.address,
        ),
        port=port,
    )


@pytest.mark.asyncio
async def test_deploy_contract(contracts):
    oracle, registry, summary = contracts
    assert isinstance(oracle, Contract)
    assert isinstance(registry, Contract)
    assert isinstance(summary, Contract)


@pytest.mark.asyncio
async def test_valid_merkle_root(pragma_client: PragmaOnChainClient):
    # Add PRAGMA as Publisher
    publisher_address = pragma_client.account_address

    await wait_for_acceptance(
        await pragma_client.add_publisher(PUBLISHER_NAME, publisher_address)
    )

    # Add PRAGMA_1 as Source for PRAGMA Publisher
    await wait_for_acceptance(
        await pragma_client.add_source_for_publisher(PUBLISHER_NAME, SOURCE_1)
    )

    merkle_root = 0x31D84DD2DB2EDB4B74A651B0F86351612EFDEDC51B51A178D5967A3CDFD319F

    timestamp = int(time.time())
    generic_entry = GenericEntry(
        DERIBIT_MERKLE_FEED_KEY,
        merkle_root,
        timestamp,
        SOURCE_1,
        PUBLISHER_NAME,
    )

    invocations = await pragma_client.publish_many([generic_entry])
    await invocations[len(invocations) - 1].wait_for_acceptance()

    # Get GENERIC
    res = await pragma_client.get_generic(DERIBIT_MERKLE_FEED_KEY)
    assert res.key == DERIBIT_MERKLE_FEED_KEY
    assert (
        res.value == 0x31D84DD2DB2EDB4B74A651B0F86351612EFDEDC51B51A178D5967A3CDFD319F
    )
    assert res.base.timestamp == timestamp
    assert felt_to_str(res.base.source) == SOURCE_1
    assert felt_to_str(res.base.publisher) == PUBLISHER_NAME

    # Update Options Data

    merkle_proof = [
        0x78626D4F8F1E24C24A41D90457688B436463D7595C4DD483671B1D5297518D2,
        0x14EB21A8E98FBD61F20D0BBDBA2B32CB2BCB61082DFCF5229370ACA5B2DBD2,
        0x73A5B6AB2F3ED2647ED316E5D4ACAC4DB4B5F8DA8F6E4707E633EBE02006043,
        0x1C156B5DEDC44A27E73968EBE3D464538D7BB0332F1C8191B2EB4A5AFCA8C7A,
        0x39B52EE5F605F57CC893D398B09CB558C87EC9C956E11CD066DF82E1006B33B,
        0x698EA138D770764C65CB171627C57EBC1EFB7C495B2C7098872CB485FD2E0BC,
        0x313F2D7DC97DABC9A7FEA0B42A5357787CABE78CDCCA0D8274EABE170AAA79D,
        0x6B35594EE638D1BAA9932B306753FBD43A300435AF0D51ABD3DD7BD06159E80,
        0x6E9F8A80EBEBAC7BA997448A1C50CD093E1B9C858CAC81537446BAFA4AA9431,
        0x3082DC1A8F44267C1B9BEA29A3DF4BD421E9C33EE1594BF297A94DFD34C7AE4,
        0x16356D27FC23E31A3570926C593BB37430201F51282F2628780264D3A399867,
    ]

    update_data: OptionData = OptionData(
        instrument_name="BTC-16AUG24-52000-P",
        base_currency="BTC",
        current_timestamp=1722805873,
        mark_price=45431835920,
    )

    await pragma_client.update_options_data(merkle_proof, update_data)

    # Check that storage was updated
    updated_data = await pragma_client.get_options_data("BTC-16AUG24-52000-P")
    assert updated_data == update_data
