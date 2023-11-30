# pylint: disable=redefined-outer-name
"""
Taken from starknet_py tests :
https://github.com/software-mansion/starknet.py/blob/0243f05ebbefc59e1e71d4aee3801205a7783645/starknet_py/tests/e2e/contract_interaction/v1_interaction_test.py
"""

import sys
from typing import List, Tuple

import pytest
import pytest_asyncio
from starknet_py.hash.address import compute_address
from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.gateway_client import GatewayClient
from starknet_py.net.http_client import GatewayHttpClient
from starknet_py.net.models import StarknetChainId
from starknet_py.net.signer.stark_curve_signer import KeyPair

from pragma.tests.constants import (
    DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
    DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
    INTEGRATION_ACCOUNT_ADDRESS,
    INTEGRATION_ACCOUNT_PRIVATE_KEY,
    TESTNET_ACCOUNT_ADDRESS,
    TESTNET_ACCOUNT_PRIVATE_KEY,
)


@pytest_asyncio.fixture(scope="package")
async def address_and_private_key(
    pytestconfig,
) -> Tuple[str, str]:
    """
    Returns address and private key of an account, depending on the network.
    """
    net = pytestconfig.getoption("--net")

    account_details = {
        "devnet": (
            DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
            DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
        ),
        "testnet": (TESTNET_ACCOUNT_ADDRESS, TESTNET_ACCOUNT_PRIVATE_KEY),
        "integration": (
            INTEGRATION_ACCOUNT_ADDRESS,
            INTEGRATION_ACCOUNT_PRIVATE_KEY,
        ),
        "fork_devnet": (
            DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
            DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
        ),
    }
    return account_details[net]


@pytest.fixture(scope="package")
def gateway_account(
    address_and_private_key: Tuple[str, str], gateway_client: GatewayClient
) -> Account:
    """
    Returns a new Account created with GatewayClient.
    """
    address, private_key = address_and_private_key

    return Account(
        address=address,
        client=gateway_client,
        key_pair=KeyPair.from_private_key(int(private_key, 0)),
        chain=StarknetChainId.TESTNET,
    )


@pytest.fixture(scope="package")
def full_node_account(
    address_and_private_key: Tuple[str, str], full_node_client: FullNodeClient
) -> Account:
    """
    Returns a new Account created with FullNodeClient.
    """
    address, private_key = address_and_private_key

    return Account(
        address=address,
        client=full_node_client,
        key_pair=KeyPair.from_private_key(int(private_key, 0)),
        chain=StarknetChainId.TESTNET,
    )


def net_to_base_accounts() -> List[str]:
    if "--client=gateway" in sys.argv:
        return ["gateway_account"]
    if "--client=full_node" in sys.argv:
        return ["full_node_account"]

    accounts = ["gateway_account"]
    nets = ["--net=integration", "--net=testnet", "testnet", "integration"]

    if set(nets).isdisjoint(sys.argv):
        accounts.extend(["full_node_account"])
    return accounts


@pytest.fixture(
    scope="package",
    params=net_to_base_accounts(),
)
def account(request) -> Account:
    """
    This parametrized fixture returns all new Accounts, one by one.
    """
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="package")
def pre_deployed_account_with_validate_deploy(pytestconfig, network: str) -> Account:
    """
    Returns an Account pre-deployed on specified network. Used to deploy other accounts.
    """
    address_and_priv_key = {
        "devnet": (
            DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS,
            DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY,
        ),
        "testnet": (TESTNET_ACCOUNT_ADDRESS, TESTNET_ACCOUNT_PRIVATE_KEY),
        "integration": (
            INTEGRATION_ACCOUNT_ADDRESS,
            INTEGRATION_ACCOUNT_PRIVATE_KEY,
        ),
    }

    net = pytestconfig.getoption("--net")
    address, private_key = address_and_priv_key[net]

    return Account(
        address=address,
        client=FullNodeClient(node_url=network),
        key_pair=KeyPair.from_private_key(int(private_key, 16)),
        chain=StarknetChainId.TESTNET,
    )
