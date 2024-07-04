import json
import random
import subprocess
import time
from typing import Any, Dict

import pytest
import requests
from pragma.common.logger import get_stream_logger
from pragma.onchain.constants import RPC_URLS
from pragma.tests.fixtures.devnet import get_available_port
from pragma.onchain.client import PragmaOnChainClient
from pragma.tests.fetchers.fetcher_configs import (
    FETCHER_CONFIGS,
    FUTURE_FETCHER_CONFIGS,
    ONCHAIN_FETCHER_CONFIGS,
    PUBLISHER_NAME,
)
from pragma.tests.constants import SAMPLE_PAIRS

logger = get_stream_logger()


@pytest.fixture(scope="package")
def network_config(request: pytest.FixtureRequest) -> Dict[str, Any]:
    """
    Fixture to provide network configuration.
    """
    return {
        "network": getattr(request, "param", {}).get("network", "mainnet"),
        "account_address": getattr(request, "param", {}).get(
            "account_address",
            "0x02356b628D108863BAf8644c945d97bAD70190AF5957031f4852d00D0F690a77",
        ),
        "block_number": getattr(request, "param", {}).get("block_number", None),
    }


@pytest.fixture(scope="package")
def forked_client(network_config: Dict[str, Any]) -> PragmaOnChainClient:
    """
    This package-scope fixture prepares a forked starknet
    client for e2e testing.

    :param network_config: Configuration for the network
    :return: a starknet Client
    """
    port = get_available_port()

    network = network_config["network"]
    account_address = network_config["account_address"]
    block_number = network_config["block_number"]

    rpc_url = random.choice(RPC_URLS[network])
    command = [
        "starknet-devnet",
        "--fork-network",
        str(rpc_url),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
        "--chain-id",
        network.upper(),
    ]
    if block_number is not None:
        print(f"forking starknet at block {block_number}")
        command.extend(["--fork-block-number", str(block_number)])

    subprocess.Popen(command)
    time.sleep(10)

    devnet_url = f"http://127.0.0.1:{port}/rpc"

    pragma_client = PragmaOnChainClient(
        devnet_url,
        chain_name=network,
        account_contract_address=account_address,
        account_private_key="0x"
        + "1" * 62,  # Dummy private key as it will use account impersonation
    )

    impersonate_account(account_address, devnet_url)

    return pragma_client


def impersonate_account(account_address: str, rpc_url: str):
    """
    Impersonates the account on the running devnet.
    see https://0xspaceshard.github.io/starknet-devnet-rs/docs/account-impersonation#devnet_impersonateaccount

    :param account_address: The account address to impersonate
    :param rpc_url: The RPC URL of the devnet
    """

    impersonate_payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "devnet_impersonateAccount",
        "params": {"account_address": account_address},
    }

    response = requests.post(rpc_url, json=impersonate_payload)

    if response.status_code != 200:
        raise Exception(f"Failed to impersonate account: {response.text}")

    result = response.json()
    if "error" in result:
        raise Exception(f"Failed to impersonate account: {result['error']}")

    logger.info(f"Successfully impersonated account: {account_address}")


@pytest.fixture
def mock_data(fetcher_config):
    with open(fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@pytest.fixture(params=FETCHER_CONFIGS.values())
def fetcher_config(request):
    return request.param


@pytest.fixture
def mock_future_data(future_fetcher_config):
    with open(future_fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@pytest.fixture(params=FUTURE_FETCHER_CONFIGS.values())
def future_fetcher_config(request):
    return request.param


@pytest.fixture(params=ONCHAIN_FETCHER_CONFIGS.values())
def onchain_fetcher_config(request):
    return request.param


@pytest.fixture
def onchain_mock_data(onchain_fetcher_config):
    with open(onchain_fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@pytest.fixture
def other_mock_endpoints(future_fetcher_config):
    # fetchers such as OkxFutureFetcher and BinanceFutureFetcher
    # have other API endpoints that must be mocked
    fetcher = future_fetcher_config["fetcher_class"](SAMPLE_PAIRS, PUBLISHER_NAME)
    other_mock_fns = future_fetcher_config.get("other_mock_fns", {})
    if not other_mock_fns:
        return []

    responses = []
    for asset in SAMPLE_PAIRS:
        base_asset = asset.base_currency.id
        for mock_fn in other_mock_fns:
            [*fn], [*val] = zip(*mock_fn.items())
            fn, val = fn[0], val[0]
            url = getattr(fetcher, fn)(**val["kwargs"][base_asset])
            with open(val["mock_file"], "r", encoding="utf-8") as filepath:
                mock_file = json.load(filepath)
            responses.append({"url": url, "json": mock_file[base_asset]})
    return responses
