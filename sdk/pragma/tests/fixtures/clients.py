import pytest
from starknet_py.net.full_node_client import FullNodeClient


@pytest.fixture(
    scope="package",
)
def client(network: str) -> FullNodeClient:
    """
    Returns Client instances.
    """
    return FullNodeClient(node_url=network)
