# pylint: disable=redefined-outer-name

import json
import subprocess
import time
from unittest import mock

import aiohttp
import pytest
import requests_mock
from aioresponses import aioresponses
from starknet_py.net.client import Client

from pragma.core.client import PragmaClient
from pragma.publisher.fetchers.avnu import AvnuFetcher
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import (
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
    SAMPLE_ONCHAIN_ASSETS,
)
from pragma.tests.fetcher_configs import (
    FETCHER_CONFIGS,
    FUTURE_FETCHER_CONFIGS,
    ONCHAIN_FETCHER_CONFIGS,
    PUBLISHER_NAME,
)
from pragma.tests.fixtures.devnet import get_available_port, get_compiler_manifest

PUBLISHER_NAME = "TEST_PUBLISHER"


# %% SPOT


@pytest.fixture(scope="module")
def forked_client(module_mocker, pytestconfig) -> Client:
    """
    This module-scope fixture prepares a forked starknet-dev
    client for e2e testing.

    :return: a starknet Client
    """
    # net = pytestconfig.getoption("--net")
    port = get_available_port()
    command = [
        "poetry",
        "run",
        "starknet-devnet",
        "--fork-network",
        "alpha-mainnet",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",  # deploys specified number of accounts
        str(1),
        "--seed",  # generates same accounts each time
        str(1),
        *get_compiler_manifest(),
    ]
    subprocess.Popen(command)  # pylint: disable=consider-using-with
    time.sleep(10)
    pragma_client = PragmaClient(f"http://127.0.0.1:{port}/rpc", chain_name="mainnet")
    module_mocker.patch.object(
        AvnuFetcher,
        "_pragma_client",
        return_value=pragma_client,
    )
    return pragma_client.client


@pytest.fixture(params=FETCHER_CONFIGS.values())
def fetcher_config(request):
    return request.param


@pytest.fixture
def mock_data(fetcher_config):
    with open(fetcher_config["mock_file"], "r", encoding="utf-8") as filepath:
        return json.load(filepath)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_fetcher(fetcher_config, mock_data, forked_client):
    # we only want to mock the external fetcher APIs and not the RPC
    with aioresponses(passthrough=[forked_client.url]) as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]

            # FIXME: Adapt all fetchers and use `sync` decorator on fetchers
            if fetcher_config["name"] == "AVNU":
                url = await fetcher.format_url_async(quote_asset, base_asset)
            else:
                url = fetcher.format_url(quote_asset, base_asset)

            if fetcher_config["name"] == "TheGraph":
                query = fetcher.query_body(quote_asset)
                mock.post(
                    url,
                    status=200,
                    body={"query": query},
                    payload=mock_data[quote_asset],
                )
            else:
                mock.get(url, status=200, payload=mock_data[quote_asset])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        assert result == fetcher_config["expected_result"]


@pytest.mark.asyncio
async def test_async_fetcher_404_error(fetcher_config, forked_client):
    with aioresponses(passthrough=[forked_client.url]) as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            # FIXME: Adapt all fetchers and use `sync` decorator on fetchers
            if fetcher_config["name"] == "AVNU":
                url = await fetcher.format_url_async(quote_asset, base_asset)
            else:
                url = fetcher.format_url(quote_asset, base_asset)

            mock.get(url, status=404)
            mock.post(url, status=404)

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

        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)

            if fetcher_config["name"] == "TheGraph":
                query = fetcher.query_body(quote_asset)
                print(query)
                mocker.post(
                    url,
                    json=mock_data[quote_asset],
                    additional_matcher=lambda request: request.text
                    == '{"query": "' + query + '"}}',
                )
            else:
                mocker.get(url, json=mock_data[quote_asset])

        result = fetcher.fetch_sync()

        assert result == fetcher_config["expected_result"]


def test_fetcher_sync_404(fetcher_config):
    with requests_mock.Mocker() as mocker:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mocker.get(url, status_code=404)
            mocker.post(url, status_code=404)

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
