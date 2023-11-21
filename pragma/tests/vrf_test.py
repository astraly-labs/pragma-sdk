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
from starknet_py.transaction_errors import TransactionRevertedError


@pytest_asyncio.fixture(scope="package")
async def declare_deploy_randomness(
    account: Account,
) -> Tuple[DeclareResult, DeployResult]:
    compiled_contract = read_contract("pragma_Randomness.sierra.json", directory=None)
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
        constructor_args=[account.address, account.signer.public_key],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    # Deploy Randomness Example
    deploy_example_result = await declare_example_result.deploy(
        constructor_args=[deploy_result.deployed_contract.address], auto_estimate=True
    )
    await deploy_example_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_example_result


@pytest_asyncio.fixture(scope="package")
# pylint: disable=redefined-outer-name
async def randomness_contracts(declare_deploy_randomness) -> (Contract, Contract):
    _, deploy_result, deploy_example_result = declare_deploy_randomness
    return (deploy_result.deployed_contract, deploy_example_result.deployed_contract)


@pytest_asyncio.fixture(scope="package", name="vrf_pragma_client")
async def vrf_pragma_client(
    randomness_contracts: (Contract, Contract),
    network,
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    (randomness, _) = randomness_contracts
    address, private_key = address_and_private_key

    # Parse port from network url
    port = urlparse(network).port

    client = PragmaClient(
        network="devnet",
        account_contract_address=address,
        account_private_key=private_key,
        port=port,
    )
    client.init_randomness_contract(randomness.address)
    return client


@pytest.mark.asyncio
async def test_deploy_contract(randomness_contracts):
    (randomness, example_randomness) = randomness_contracts
    assert isinstance(randomness, Contract)
    assert isinstance(example_randomness, Contract)


@pytest.mark.asyncio
# pylint: disable=redefined-outer-name
async def test_client_setup(vrf_pragma_client: PragmaClient, account: Account):
    assert vrf_pragma_client.account_address() == account.address

    account_balance = await account.get_balance()
    assert await vrf_pragma_client.get_balance(account.address) == account_balance

    assert vrf_pragma_client.randomness is not None


@pytest.mark.asyncio
async def test_randomness_mixin(vrf_pragma_client: PragmaClient, randomness_contracts: (Contract, Contract), address_and_private_key):
    _, private_key = address_and_private_key
    (randomness, example_randomness) = randomness_contracts

    seed = 1
    callback_gas_limit = 1000000
    callback_address = example_randomness.address
    publish_delay = 0
    num_words = 1
    caller_address = vrf_pragma_client.account_address()

    await vrf_pragma_client.request_random(seed, callback_address, callback_gas_limit, publish_delay, num_words)
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [0]

    await vrf_pragma_client.handle_random(int(private_key, 16), min_block=0)
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []

    status = await vrf_pragma_client.get_request_status(caller_address, 0)
    assert status.variant == 'FULFILLED'

    # Request cancellation test
    seed = 2
    await vrf_pragma_client.request_random(seed, callback_address, callback_gas_limit, publish_delay, num_words)
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [1]
    status = await vrf_pragma_client.get_request_status(caller_address, 1)
    assert status.variant == 'RECEIVED'
    await vrf_pragma_client.cancel_random_request(pending_reqs[0], caller_address, seed,callback_address, callback_gas_limit,publish_delay, num_words)
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []
    status = await vrf_pragma_client.get_request_status(caller_address, 1)
    assert status.variant == 'CANCELLED'

    # Request cancellation failed if request is already fulfilled
    seed = 3
    await vrf_pragma_client.request_random(seed, callback_address, callback_gas_limit, publish_delay, num_words)
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == [2]
    status = await vrf_pragma_client.get_request_status(caller_address, 2)
    assert status.variant == 'RECEIVED'
    await vrf_pragma_client.handle_random(int(private_key, 16), min_block=0)
    pending_reqs = await vrf_pragma_client.get_pending_requests(caller_address)
    assert pending_reqs == []
    status = await vrf_pragma_client.get_request_status(caller_address, 2)
    assert status.variant == 'FULFILLED'
    try: 
        await vrf_pragma_client.cancel_random_request(2, caller_address, seed,callback_address, callback_gas_limit,publish_delay, num_words)
        assert False
    except TransactionRevertedError as err: 
        err_msg = "Execution was reverted; failure reason: [0x7265717565737420616c72656164792066756c66696c6c6564]"
        if not err_msg in err.message:
            raise err
        
    
        
    


