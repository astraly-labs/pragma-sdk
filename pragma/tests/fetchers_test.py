# pylint: disable=redefined-outer-name

import json
import math
import random
import subprocess
import time
from unittest import mock

import aiohttp
import pytest
import requests_mock
from aioresponses import aioresponses
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client import Client
from starknet_py.net.client_models import Call

from pragma.core.client import PragmaClient
from pragma.core.types import RPC_URLS, get_client_from_network
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import (
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
    SAMPLE_ONCHAIN_ASSETS,
    STARKNET_ONCHAIN_ASSETS,
    STARKNET_SAMPLE_ASSETS,
)
from pragma.tests.fetcher_configs import (
    FETCHER_CONFIGS,
    FUTURE_FETCHER_CONFIGS,
    ONCHAIN_FETCHER_CONFIGS,
    ONCHAIN_STARKNET_FETCHER_CONFIGS,
    PUBLISHER_NAME,
)
from pragma.tests.fixtures.devnet import get_available_port

PUBLISHER_NAME = "TEST_PUBLISHER"
JEDISWAP_POOL = "0x4e021092841c1b01907f42e7058f97e5a22056e605dce08a22868606ad675e0"


# %% SPOT


@pytest.fixture(scope="module")
def forked_client(request, module_mocker, pytestconfig) -> Client:
    """
    This module-scope fixture prepares a forked katana
    client for e2e testing.

    :return: a starknet Client
    """
    # net = pytestconfig.getoption("--net")
    port = get_available_port()
    block_number = request.param.get("block_number", None)
    network = request.param.get("network", "mainnet")

    rpc_url = RPC_URLS[network][random.randint(0, len(RPC_URLS[network]) - 1)]
    command = [
        "katana",
        "--rpc-url",
        str(rpc_url),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
        "--disable-fee",
    ]
    if block_number is not None:
        print(f"forking katana at block {block_number}")
        command.extend(["--fork-block-number", str(block_number)])
    subprocess.Popen(command)  # pylint: disable=consider-using-with
    time.sleep(10)
    pragma_client = PragmaClient(f"http://127.0.0.1:{port}/rpc", chain_name=network)
    return pragma_client


@pytest.fixture(params=FETCHER_CONFIGS.values())
def fetcher_config(request):
    return request.param


@pytest.fixture
def mock_data(fetcher_config):
    with open(fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.parametrize(
    "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
)
@pytest.mark.asyncio
async def test_async_fetcher(fetcher_config, mock_data, forked_client):
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses(passthrough=[forked_client.client.url]) as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)
        array_starknet = []
        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]

            # FIXME: Adapt all fetchers and use `sync` decorator on fetchers

            url = fetcher.format_url(quote_asset, base_asset)

            if fetcher_config["name"] == "TheGraph":
                query = fetcher.query_body(quote_asset)
                mock.post(
                    url,
                    status=200,
                    body={"query": query},
                    payload=mock_data[quote_asset],
                )
            elif fetcher_config["name"] == "Starknet":
                continue
            else:
                mock.get(url, status=200, payload=mock_data[quote_asset])

        if fetcher_config["name"] == "Starknet":
            async with aiohttp.ClientSession() as session:
                for asset in STARKNET_SAMPLE_ASSETS:
                    quote_asset = asset["pair"][0]
                    base_asset = asset["pair"][1]
                    url = fetcher.format_url(
                        quote_asset, base_asset, "2024-01-01T00%3A00%3A00"
                    )
                    mock.get(url, status=200, payload=mock_data[quote_asset])
                    price = await fetcher.off_fetch_ekubo_price(
                        asset, session, "2024-01-01T00%3A00%3A00"
                    )
                    array_starknet.append(price)
        if fetcher_config["name"] != "Starknet":
            async with aiohttp.ClientSession() as session:
                result = await fetcher.fetch(session)
            assert result == fetcher_config["expected_result"]
        else:
            for i in range(len(array_starknet)):
                assert (
                    float(array_starknet[i])
                    == fetcher_config["expected_result"][i].price / 10**18
                )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "forked_client", [{"block_number": None, "network": "mainnet"}], indirect=True
)
async def test_async_fetcher_404_error(fetcher_config, forked_client):
    array_starknet = []
    with aioresponses(passthrough=[forked_client.client.url]) as mock:
        if fetcher_config["name"] == "Starknet":
            async with aiohttp.ClientSession() as session:
                fetcher = fetcher_config["fetcher_class"](
                    STARKNET_SAMPLE_ASSETS, PUBLISHER_NAME
                )
                for asset in STARKNET_SAMPLE_ASSETS:
                    quote_asset = asset["pair"][0]
                    base_asset = asset["pair"][1]
                    url = fetcher.format_url(
                        quote_asset, base_asset, "2024-01-01T00%3A00%3A00"
                    )
                    mock.get(url, status=404)
                    mock.post(url, status=404)
                    price = await fetcher.off_fetch_ekubo_price(
                        asset, session, "2024-01-01T00%3A00%3A00"
                    )
                    array_starknet.append(price)
            expected_result = [
                PublisherFetchError(
                    f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {fetcher_config['name']}"
                )
                for asset in STARKNET_SAMPLE_ASSETS
            ]

            assert array_starknet == expected_result

        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            # FIXME: Adapt all fetchers and use `sync` decorator on fetchers

            url = fetcher.format_url(quote_asset, base_asset)

            mock.get(url, status=404)
            mock.post(url, status=404)

        if fetcher_config["name"] == "Starknet":
            pass
        else:
            async with aiohttp.ClientSession() as session:
                result = await fetcher.fetch(session)
                # Adjust the expected result to reflect the 404 error
                expected_result = [
                    PublisherFetchError(
                        f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {fetcher_config['name']}"
                    )
                    for asset in SAMPLE_ASSETS
                ]
                assert result == expected_result


@mock.patch("time.time", mock.MagicMock(return_value=12345))
def test_fetcher_sync_success(fetcher_config, mock_data):
    with requests_mock.Mocker() as mocker:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)
        array_starknet = []
        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)

            # TODO (#000): Fix this test
            if fetcher_config["name"] == "TheGraph":
                query = fetcher.query_body(quote_asset)
                print(query)
                mocker.post(
                    url,
                    json=mock_data[quote_asset],
                    additional_matcher=lambda request: request.text
                    == '{"query": "' + query + '"}}',
                )
                continue
            elif fetcher_config["name"] == "Starknet":
                continue
            else:
                mocker.get(url, json=mock_data[quote_asset])
        if fetcher_config["name"] == "Starknet":
            for asset in STARKNET_SAMPLE_ASSETS:
                quote_asset = asset["pair"][0]
                base_asset = asset["pair"][1]
                url = fetcher.format_url(
                    quote_asset, base_asset, "2024-01-01T00%3A00%3A00"
                )
                mocker.get(url, json=mock_data[quote_asset])
                array_starknet.append(
                    fetcher.off_fetch_ekubo_price_sync(asset, "2024-01-01T00%3A00%3A00")
                )
        if fetcher_config["name"] != "Starknet":
            result = fetcher.fetch_sync()
            assert result == fetcher_config["expected_result"]
        else:
            result = array_starknet
            for i in range(len(result)):
                assert (
                    float(result[i])
                    == fetcher_config["expected_result"][i].price / 10**18
                )


def test_fetcher_sync_404(fetcher_config):
    array_starknet = []
    with requests_mock.Mocker() as mocker:
        if fetcher_config["name"] == "Starknet":
            fetcher = fetcher_config["fetcher_class"](
                STARKNET_SAMPLE_ASSETS, PUBLISHER_NAME
            )
            for asset in STARKNET_SAMPLE_ASSETS:
                quote_asset = asset["pair"][0]
                base_asset = asset["pair"][1]
                url = fetcher.format_url(
                    quote_asset, base_asset, "2024-01-01T00%3A00%3A00"
                )
                mocker.get(url, status_code=404)
                mocker.post(url, status_code=404)
                price = fetcher.off_fetch_ekubo_price_sync(
                    asset, "2024-01-01T00%3A00%3A00"
                )
                array_starknet.append(price)

            expected_result = [
                PublisherFetchError(
                    f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {fetcher_config['name']}"
                )
                for asset in STARKNET_SAMPLE_ASSETS
            ]
            assert array_starknet == expected_result

        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, status_code=404)
            mocker.post(url, status_code=404)

        if fetcher_config["name"] == "Starknet":
            pass
        else:
            result = fetcher.fetch_sync()
            # Adjust the expected result to reflect the 404 error
            expected_result = [
                PublisherFetchError(
                    f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {fetcher_config['name']}"
                )
                for asset in SAMPLE_ASSETS
            ]

            assert result == expected_result


# %% FUTURE


@pytest.fixture(params=FUTURE_FETCHER_CONFIGS.values())
def future_fetcher_config(request):
    return request.param


@pytest.fixture
def other_mock_endpoints(future_fetcher_config):
    # fetchers such as OkxFutureFetcher and BinanceFutureFetcher
    # have other API endpoints that must be mocked
    fetcher = future_fetcher_config["fetcher_class"](
        SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
    )
    other_mock_fns = future_fetcher_config.get("other_mock_fns", {})
    if not other_mock_fns:
        return []

    responses = []
    for asset in SAMPLE_FUTURE_ASSETS:
        quote_asset = asset["pair"][0]
        for mock_fn in other_mock_fns:
            [*fn], [*val] = zip(*mock_fn.items())
            fn, val = fn[0], val[0]
            url = getattr(fetcher, fn)(**val["kwargs"][quote_asset])
            with open(val["mock_file"], "r", encoding="utf-8") as filepath:
                mock_file = json.load(filepath)
            responses.append({"url": url, "json": mock_file[quote_asset]})
    return responses


@pytest.fixture
def mock_future_data(future_fetcher_config):
    with open(future_fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_future_fetcher(
    future_fetcher_config, mock_future_data, other_mock_endpoints
):
    with aioresponses() as mock:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=200, payload=mock_future_data[quote_asset])

        if other_mock_endpoints:
            for endpoint in other_mock_endpoints:
                mock.get(endpoint["url"], status=200, payload=endpoint["json"])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        assert result == future_fetcher_config["expected_result"]


@pytest.mark.asyncio
async def test_async_future_fetcher_404_error(future_fetcher_config):
    with aioresponses() as mock:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {future_fetcher_config['name']}"
            )
            for asset in SAMPLE_FUTURE_ASSETS
        ]

        assert result == expected_result


@mock.patch("time.time", mock.MagicMock(return_value=12345))
def test_future_fetcher_sync_success(
    future_fetcher_config, mock_future_data, other_mock_endpoints
):
    with requests_mock.Mocker() as mock:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, json=mock_future_data[quote_asset])

        if other_mock_endpoints:
            for endpoint in other_mock_endpoints:
                mock.get(endpoint["url"], json=endpoint["json"])

        result = fetcher.fetch_sync()

        assert result == future_fetcher_config["expected_result"]


def test_future_fetcher_sync_404(future_fetcher_config):
    with requests_mock.Mocker() as mocker:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, status_code=404)

        result = fetcher.fetch_sync()

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {future_fetcher_config['name']}"
            )
            for asset in SAMPLE_FUTURE_ASSETS
        ]

        assert result == expected_result


# %% ONCHAIN


@pytest.fixture(params=ONCHAIN_FETCHER_CONFIGS.values())
def onchain_fetcher_config(request):
    return request.param


@pytest.fixture
def onchain_mock_data(onchain_fetcher_config):
    with open(onchain_fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_onchain_async_fetcher(onchain_fetcher_config, onchain_mock_data):
    with aioresponses() as mock:
        fetcher = onchain_fetcher_config["fetcher_class"](
            SAMPLE_ONCHAIN_ASSETS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in SAMPLE_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=200, payload=onchain_mock_data[quote_asset])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)
        assert result == onchain_fetcher_config["expected_result"]


@pytest.mark.asyncio
async def test_onchain_async_fetcher_404_error(onchain_fetcher_config):
    with aioresponses() as mock:
        fetcher = onchain_fetcher_config["fetcher_class"](
            SAMPLE_ONCHAIN_ASSETS, PUBLISHER_NAME
        )

        for asset in SAMPLE_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {onchain_fetcher_config['name']}"
            )
            for asset in SAMPLE_ONCHAIN_ASSETS
        ]

        assert result == expected_result


@mock.patch("time.time", mock.MagicMock(return_value=12345))
def test_onchain_fetcher_sync_success(onchain_fetcher_config, onchain_mock_data):
    with requests_mock.Mocker() as mocker:
        fetcher = onchain_fetcher_config["fetcher_class"](
            SAMPLE_ONCHAIN_ASSETS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in SAMPLE_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, json=onchain_mock_data[quote_asset])

        result = fetcher.fetch_sync()

        assert result == onchain_fetcher_config["expected_result"]


def test_onchain_fetcher_sync_404(onchain_fetcher_config):
    with requests_mock.Mocker() as mocker:
        fetcher = onchain_fetcher_config["fetcher_class"](
            SAMPLE_ONCHAIN_ASSETS, PUBLISHER_NAME
        )

        for asset in SAMPLE_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, status_code=404)

        result = fetcher.fetch_sync()

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {onchain_fetcher_config['name']}"
            )
            for asset in SAMPLE_ONCHAIN_ASSETS
        ]

        assert result == expected_result


@pytest.fixture(params=ONCHAIN_STARKNET_FETCHER_CONFIGS.values())
def starknet_onchain_fetcher_config(request):
    return request.param


@pytest.fixture
def starknet_mock_data(starknet_onchain_fetcher_config):
    with open(
        starknet_onchain_fetcher_config["mock_file"], "r", encoding="utf-8"
    ) as filepath:
        return json.load(filepath)


@pytest.mark.parametrize(
    "forked_client", [{"block_number": 939346, "network": "testnet"}], indirect=True
)
@pytest.mark.asyncio
async def test_onchain_starknet_async_fetcher(
    starknet_onchain_fetcher_config, forked_client
):
    with requests_mock.Mocker() as mocker:
        fetcher = starknet_onchain_fetcher_config["fetcher_class"](
            STARKNET_ONCHAIN_ASSETS,
            PUBLISHER_NAME,
            client=forked_client,
        )

        for asset in STARKNET_ONCHAIN_ASSETS:
            if asset["pair"] == ("STRK", "USD"):
                continue
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, status_code=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.on_fetch_jedi_price(session)

        expected_result = starknet_onchain_fetcher_config["expected_result"]
        assert result == expected_result[1].price


@pytest.mark.parametrize(
    "forked_client", [{"block_number": 939346, "network": "testnet"}], indirect=True
)
def test_onchain_starknet_sync_fetcher(starknet_onchain_fetcher_config, forked_client):
    with requests_mock.Mocker() as mocker:
        fetcher = starknet_onchain_fetcher_config["fetcher_class"](
            STARKNET_ONCHAIN_ASSETS,
            PUBLISHER_NAME,
            client=forked_client,
        )

        # Mocking the expected call for assets
        for asset in STARKNET_ONCHAIN_ASSETS:
            if asset["pair"] == ("STRK", "USD"):
                continue
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, status_code=404)

        result = fetcher.on_fetch_jedi_price_sync()

        expected_result = starknet_onchain_fetcher_config["expected_result"]
        assert result == expected_result[1].price


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.parametrize(
    "forked_client", [{"block_number": 939346, "network": "testnet"}], indirect=True
)
@pytest.mark.asyncio  # Mark the test as an asyncio test
async def test_onchain_starknet_async_fetcher_full(
    starknet_onchain_fetcher_config, forked_client, starknet_mock_data
):
    with aioresponses(passthrough=[forked_client.client.url]) as m:
        fetcher = starknet_onchain_fetcher_config["fetcher_class"](
            STARKNET_ONCHAIN_ASSETS,
            PUBLISHER_NAME,
            client=forked_client,
        )

        for asset in STARKNET_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, status=404)  # Use status for aiohttp
            if asset["pair"] == ("STRK", "USD"):
                m.get(
                    "https://coins.llama.fi/prices/current/coingecko:ethereum?searchWidth=5m",
                    status=200,
                    body=starknet_mock_data["ETH"],
                )

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(
                session
            )  # Make sure the fetch method is awaited

        expected_result = starknet_onchain_fetcher_config["expected_result"]
        for element in expected_result:
            element.price = math.floor(element.price * 10**8)
        assert result == expected_result


# TODO: Write sync version of the oracle mixin before uncommenting this
# @mock.patch("time.time", mock.MagicMock(return_value=12345))
# @pytest.mark.parametrize(
#     "forked_client", [{"block_number": 939346, "network": "testnet"}], indirect=True
# )
# def test_onchain_starknet_sync_fetcher_full(
#     starknet_onchain_fetcher_config, forked_client, starknet_mock_data
# ):
#     with requests_mock.Mocker() as mocker:
#         fetcher = starknet_onchain_fetcher_config["fetcher_class"](
#             STARKNET_ONCHAIN_ASSETS,
#             PUBLISHER_NAME,
#             client=forked_client.full_node_client,
#         )

#         for asset in STARKNET_ONCHAIN_ASSETS:
#             quote_asset = asset["pair"][0]
#             base_asset = asset["pair"][1]
#             url = fetcher.format_url(quote_asset, base_asset)
#             mocker.get(url, status_code=404)
#             if asset["pair"] == ("STRK", "USD"):
#                 mocker.get(
#                     "https://coins.llama.fi/prices/current/coingecko:ethereum?searchWidth=5m",
#                     status_code=200,
#                     json=starknet_mock_data["ETH"],
#                 )

#         result = fetcher.fetch_sync()

#         expected_result = starknet_onchain_fetcher_config["expected_result"]
#         assert result == expected_result
