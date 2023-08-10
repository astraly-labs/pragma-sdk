# pylint: disable=redefined-outer-name


import pytest
from starknet_py.net.models.typed_data import TypedData


def pytest_addoption(parser):
    parser.addoption(
        "--net",
        action="store",
        default="devnet",
        help="Network to run tests on: possible 'testnet', 'devnet', 'all'",
    )


@pytest.fixture(scope="package")
def network(pytestconfig, run_devnet: str) -> str:
    """
    Returns network address depending on the --net parameter.
    """
    net = pytestconfig.getoption("--net")
    net_address = {
        "devnet": run_devnet,
        "testnet": "testnet",
        "integration": "https://external.integration.starknet.io",
    }

    return net_address[net]
