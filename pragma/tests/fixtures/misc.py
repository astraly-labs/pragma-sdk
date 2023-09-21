# pylint: disable=redefined-outer-name


import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--net",
        action="store",
        default="devnet",
        help="Network to run tests on: possible 'testnet', 'devnet', 'all'",
    )
    parser.addoption(
        "--client",
        action="store",
        default="",
        help="Client to run tests with: possible 'gateway', 'full_node'",
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


def pytest_collection_modifyitems(config, items):
    if config.getoption("--net") == "all":
        return

    run_testnet = config.getoption("--net") == "testnet"
    run_devnet = config.getoption("--net") == "devnet"
    for item in items:
        runs_on_testnet = "run_on_testnet" in item.keywords
        runs_on_devnet = "run_on_devnet" in item.keywords
        should_not_run = (runs_on_devnet and not run_devnet) or (
            runs_on_testnet and not run_testnet
        )
        if should_not_run:
            item.add_marker(pytest.mark.skip())


@pytest.fixture(name="tx_receipt_full_node_path", scope="package")
def get_tx_receipt_full_node_client():
    return "starknet_py.net.full_node_client.FullNodeClient.get_transaction_receipt"


@pytest.fixture(name="tx_receipt_gateway_path", scope="package")
def get_tx_receipt_gateway_client():
    return "starknet_py.net.gateway_client.GatewayClient.get_transaction_receipt"
