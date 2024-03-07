"""
Taken from
https://github.com/software-mansion/starknet.py/blob/0243f05ebbefc59e1e71d4aee3801205a7783645/starknet_py/tests/e2e/contract_interaction/v1_interaction_test.py
"""

import sys
from typing import List

import pytest
from starknet_py.net.client import Client
from starknet_py.net.full_node_client import FullNodeClient


@pytest.fixture(name="full_node_client", scope="package")
def create_full_node_client(network: str) -> FullNodeClient:
    """
    Creates and returns FullNodeClient.
    """
    return FullNodeClient(node_url=network)


def net_to_clients() -> List[str]:
    """
    Return client fixture names based on network in sys.argv.
    """
    return ["full_node_client"]


@pytest.fixture(
    scope="package",
    params=net_to_clients(),
)
def client(request) -> Client:
    """
    Returns Client instances.
    """
    return request.getfixturevalue(request.param)
