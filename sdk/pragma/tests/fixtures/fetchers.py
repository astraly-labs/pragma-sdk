import json
import random
import subprocess
import time

import pytest
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


@pytest.fixture(scope="module")
def forked_client(request) -> PragmaOnChainClient:
    """
    This module-scope fixture prepares a forked starknet
    client for e2e testing.

    :return: a starknet Client
    """
    port = get_available_port()
    block_number = request.param.get("block_number", None)
    network = request.param.get("network", "mainnet")

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
    ]
    if block_number is not None:
        print(f"forking starknet at block {block_number}")
        command.extend(["--fork-block-number", str(block_number)])
    subprocess.Popen(command)
    time.sleep(10)
    pragma_client = PragmaOnChainClient(
        f"http://127.0.0.1:{port}/rpc", chain_name=network
    )
    return pragma_client


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
