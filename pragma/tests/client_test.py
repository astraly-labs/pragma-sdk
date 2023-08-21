from typing import Tuple

import pytest
import pytest_asyncio
from starknet_py.cairo.felt import decode_shortstring
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.hash.storage import get_storage_var_address
from starknet_py.net.account.base_account import BaseAccount

from pragma.core.client import PragmaClient
from pragma.core.types import ContractAddresses
from pragma.tests.constants import (
    DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
    MOCK_COMPILED_DIR,
    U128_MAX,
    U256_MAX,
    currencies,
    pairs,
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
    currencies = [currency.serialize() for currency in currencies]
    pairs = [pair.serialize() for pair in pairs]

    deploy_result = await declare_result.deploy(
        constructor_args=[
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
    contracts: (Contract, Contract), account: BaseAccount
) -> PragmaClient:
    oracle, registry = contracts
    return PragmaClient(
        network="devnet",
        account_contract_address=account.address,
        account_private_key=DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
        contract_addresses_config=ContractAddresses(registry.address, oracle.address),
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
    assert pragma_client.account_address == account.address

    account_balance = await account.get_balance()
    assert pragma_client.get_balance() == account_balance

    assert pragma_client.oracle is not None
    assert pragma_client.publisher_registry is not None


@pytest.mark.asyncio
async def test_client_publisher_mixin(pragma_client: PragmaClient, contracts):
    oracle, registry = contracts
    publishers = await pragma_client.get_all_publishers()
    assert publishers == []

    PUBLISHER_NAME = "PUBLISHER_1"

    await pragma_client.add_publisher(PUBLISHER_NAME)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [PUBLISHER_NAME]
