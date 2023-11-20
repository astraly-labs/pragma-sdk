import time
from typing import Tuple
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account


from pragma.core.client import PragmaClient
from pragma.core.entry import FutureEntry, SpotEntry
from pragma.core.types import ContractAddresses, DataType, DataTypes
from pragma.core.utils import str_to_felt
from pragma.tests.constants import CURRENCIES, PAIRS
from pragma.tests.utils import read_contract



@pytest_asyncio.fixture(scope="package")
async def declare_deploy_randomness(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract = read_contract(
        "pragma_Randomness.sierra.json", directory=None
    )
    compiled_contract_casm = read_contract(
        "pragma_Randomness.casm.json", directory=None
    )

    compiled_example_contract = read_contract(
        "pragma_ExampleRandomness.sierra.json", directory=None
    )
    compiled_example_contract_casm = read_contract(
        "pragma_ExampleRandomness.casm.json", directory=None
    )

    # Declare Randomness
    declare_result = await Contract.declare(
        account=account,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Declare Randomness Example
    declare_example_result = await Contract.declare(
        account=account,
        compiled_contract=compiled_example_contract,
        compiled_contract_casm=compiled_example_contract_casm,
        auto_estimate=True,
    )
    await declare_example_result.wait_for_acceptance()
    


    # Deploy Randomness
    deploy_result = await declare_result.deploy(
        constructor_args=[account.address, account.signer.public_key], auto_estimate=True
    )
    await deploy_result.wait_for_acceptance()

    # Deploy Randomness Example
    deploy_example_result = await declare_example_result.deploy(
        deploy_result.deployed_contract.address)
    await deploy_example_result.wait_for_acceptance()
    return declare_result, deploy_result, deploy_example_result


@pytest_asyncio.fixture(scope="package")
# pylint: disable=redefined-outer-name
async def randomness_contracts(declare_deploy_randomness) -> (Contract, Contract):
    _, deploy_result, deploy_example_result = declare_deploy_randomness
    return (deploy_result.deployed_contract, deploy_example_result.deployed_contract)


@pytest_asyncio.fixture(scope="package", name="pragma_client")
async def pragma_client(
    randomness_contracts: (Contract, Contract),
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    (randomness, _)= randomness_contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    client= PragmaClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        port=port,
    )
    await client.init_randomness_contract(randomness.address)
    return client

@pytest.mark.asyncio
async def test_deploy_contract(contracts):
    (randomness, example_randomness) = contracts
    assert isinstance(randomness, Contract)
    assert isinstance(example_randomness, Contract)


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_client_setup(pragma_client: PragmaClient, account: Account):
    assert pragma_client.account_address() == account.address

    account_balance = await account.get_balance()
    assert await pragma_client.get_balance(account.address) == account_balance

    assert pragma_client.randomness is not None
    assert pragma_client.example_randomness is not None





@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_randomness_mixin(pragma_client: PragmaClient, address_and_private_key):
    _, private_key = address_and_private_key
    print('********************************************************************12312313123213')
    seed =1
    callback_gas_limit = 0;
    callback_address = pragma_client.account_address();
    publish_delay = 1;
    num_words = 1;
    # block_number = await pragma_client.fullnode_client.get_block_number()
    last_random = await pragma_client.get_last_random()
    assert last_random == 0
    request_id = await pragma_client.request_random(seed, callback_address,callback_gas_limit, publish_delay, num_words)
    assert request_id == 1
    status = await pragma_client.get_random_status(request_id)
    assert status == 1 
    pragma_client.handle_random(private_key, 0)
    last_random = await pragma_client.get_last_random()
    assert last_random != 0
    status = await pragma_client.get_random_status(request_id)
    assert status == 2
    random_words = await pragma_client.get_random_words(request_id)
    assert random_words == [last_random]







