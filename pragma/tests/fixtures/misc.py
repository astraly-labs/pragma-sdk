import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--net",
        action="store",
        default="devnet",
        help="Network to run tests on, one of: "
        "`mainnet`, `testnet`, `sharingan`, `pragma_testnet`, `fork_devnet`",
    )
    parser.addoption(
        "--fork-block-number",
        action="store",
        default="",
        help="The block number to fork from. See: "
        "https://0xspaceshard.github.io/starknet-devnet-rs/docs/forking",
    )
    parser.addoption(
        "--client",
        action="store",
        default="",
        help="Client to run tests with: possible 'full_node'",
    )


@pytest.fixture(scope="package")
def network(pytestconfig, run_devnet: str, fork_testnet_devnet: str) -> str:
    """
    Returns network address depending on the --net parameter.
    """
    net = pytestconfig.getoption("--net")
    net_address = {
        "fork_devnet": fork_testnet_devnet,
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
    fork_testnet_devnet = config.getoption("--net") == "fork_devnet"
    for item in items:
        runs_on_testnet = "run_on_testnet" in item.keywords
        runs_on_devnet = "run_on_devnet" in item.keywords
        runs_on_fork_devnet = "run_on_fork_devnet" in item.keywords
        should_not_run = (
            (runs_on_devnet and not run_devnet)
            or (runs_on_testnet and not run_testnet)
            or (runs_on_fork_devnet and not fork_testnet_devnet)
        )
        if should_not_run:
            item.add_marker(pytest.mark.skip())


@pytest.fixture(name="tx_receipt_full_node_path", scope="package")
def get_tx_receipt_full_node_client():
    return "starknet_py.net.full_node_client.FullNodeClient.get_transaction_receipt"
