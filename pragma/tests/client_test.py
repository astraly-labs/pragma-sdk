from typing import Tuple

import pytest
import pytest_asyncio
from starknet_py.cairo.felt import decode_shortstring
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.hash.storage import get_storage_var_address

from pragma.tests.constants import MOCK_COMPILED_DIR, U128_MAX, U256_MAX
from pragma.tests.utils import read_contract


@pytest_asyncio.fixture(scope="package")
async def declare_deploy_oracle(account) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract = read_contract("pragma_Oracle.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Oracle.casm.json", directory=None)

    declare_result = await Contract.declare(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    deploy_result = await declare_result.deploy(auto_estimate=True)
    await deploy_result.wait_for_acceptance()

    return declare_result, deploy_result


@pytest_asyncio.fixture(scope="package", name="contract")
# pylint: disable=redefined-outer-name
async def oracle_contract(declare_deploy_oracle) -> Contract:
    _, deploy_result = declare_deploy_oracle
    return deploy_result.deployed_contract


@pytest.mark.asyncio
async def test_deploy_contract(contract):
    assert isinstance(contract, Contract)
