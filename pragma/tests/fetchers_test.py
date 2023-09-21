import json
from unittest import mock

import aiohttp
import pytest
import requests_mock
from aioresponses import aioresponses

from pragma.core.assets import PRAGMA_ALL_ASSETS
from pragma.core.entry import FutureEntry, SpotEntry
from pragma.publisher.fetchers import (
    AscendexFetcher,
    BitstampFetcher,
    CexFetcher,
    CoinbaseFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    KaikoFetcher,
    OkxFetcher,
)
from pragma.publisher.future_fetchers import (
    BinanceFutureFetcher,
    ByBitFutureFetcher,
    OkxFutureFetcher,
)
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import (
    MOCK_DIR,
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
    SAMPLE_ONCHAIN_ASSETS,
)

PUBLISHER_NAME = "TEST_PUBLISHER"

# Define fetcher configurations
FETCHER_CONFIGS = {
    "CexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "cex.json",
        "fetcher_class": CexFetcher,
        "name": "CEX",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2601210000000,
                1692717096,
                "CEX",
                PUBLISHER_NAME,
                volume=1.81043893,
            ),
            SpotEntry(
                "ETH/USD",
                163921000000,
                1692724899,
                "CEX",
                PUBLISHER_NAME,
                volume=56.54796900,
            ),
        ],
    },
    "DefillamaFetcher": {
        "mock_file": MOCK_DIR / "responses" / "defillama.json",
        "fetcher_class": DefillamaFetcher,
        "name": "Defillama",
        "expected_result": [
            SpotEntry(
                "BTC/USD", 2604800000000, 1692779346, "DEFILLAMA", PUBLISHER_NAME
            ),
            SpotEntry("ETH/USD", 164507000000, 1692779707, "DEFILLAMA", PUBLISHER_NAME),
        ],
    },
    "BitstampFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bitstamp.json",
        "fetcher_class": BitstampFetcher,
        "name": "Bitstamp",
        "expected_result": [
            SpotEntry("BTC/USD", 2602100000000, 1692781034, "BITSTAMP", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164250000000, 1692780986, "BITSTAMP", PUBLISHER_NAME),
        ],
    },
    "CoinbaseFetcher": {
        "mock_file": MOCK_DIR / "responses" / "coinbase.json",
        "fetcher_class": CoinbaseFetcher,
        "name": "Coinbase",
        "expected_result": [
            SpotEntry("BTC/USD", 2602820500003, 12345, "COINBASE", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 164399499999, 12345, "COINBASE", PUBLISHER_NAME),
        ],
    },
    "AscendexFetcher": {
        "mock_file": MOCK_DIR / "responses" / "ascendex.json",
        "fetcher_class": AscendexFetcher,
        "name": "Ascendex",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2602650000000,
                12345,
                "ASCENDEX",
                PUBLISHER_NAME,
                volume=9.7894,
            ),
            SpotEntry(
                "ETH/USD",
                164369999999,
                12345,
                "ASCENDEX",
                PUBLISHER_NAME,
                volume=123.188,
            ),
        ],
    },
    "OkxFetcher": {
        "mock_file": MOCK_DIR / "responses" / "okx.json",
        "fetcher_class": OkxFetcher,
        "name": "OKX",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2640240000000,
                1692829724,
                "OKX",
                PUBLISHER_NAME,
                volume=18382.3898,
            ),
            SpotEntry(
                "ETH/USD",
                167372000000,
                1692829751,
                "OKX",
                PUBLISHER_NAME,
                volume=185341.3646,
            ),
        ],
    },
    "KaikoFetcher": {
        "mock_file": MOCK_DIR / "responses" / "kaiko.json",
        "fetcher_class": KaikoFetcher,
        "name": "Kaiko",
        "expected_result": [
            SpotEntry(
                "BTC/USD",
                2601601000000,
                1692782303,
                "KAIKO",
                PUBLISHER_NAME,
                volume=0.00414884,
            ),
            SpotEntry(
                "ETH/USD",
                164315580431,
                1692782453,
                "KAIKO",
                PUBLISHER_NAME,
                volume=45.04710943999999,
            ),
        ],
    },
}

FUTURE_FETCHER_CONFIGS = {
    "ByBitFutureFetcher": {
        "mock_file": MOCK_DIR / "responses" / "bybit_future.json",
        "fetcher_class": ByBitFutureFetcher,
        "name": "BYBIT",
        "expected_result": [
            FutureEntry(
                "BTC/USD",
                2589900000000,
                1692982428,
                "BYBIT",
                PUBLISHER_NAME,
                0,
                volume=float(421181110),
            ),
            FutureEntry(
                "ETH/USD",
                164025000000,
                1692982480,
                "BYBIT",
                PUBLISHER_NAME,
                0,
                volume=float(56108213),
            ),
        ],
    },
    "OkxFutureFetcher": {
        "mock_file": MOCK_DIR / "responses" / "okx_future" / "ticker.json",
        "fetcher_class": OkxFutureFetcher,
        "name": "OKX",
        "other_mock_fns": [
            {
                "format_expiry_timestamp_url": {
                    "kwargs": {
                        "BTC": {"id": "BTC-USD-230922"},
                        "ETH": {"id": "ETH-USD-230922"},
                    },
                    "mock_file": MOCK_DIR
                    / "responses"
                    / "okx_future"
                    / "timestamp_230922.json",
                }
            },
            {
                "format_expiry_timestamp_url": {
                    "kwargs": {
                        "BTC": {"id": "BTC-USD-230929"},
                        "ETH": {"id": "ETH-USD-230929"},
                    },
                    "mock_file": MOCK_DIR
                    / "responses"
                    / "okx_future"
                    / "timestamp_230929.json",
                }
            },
        ],
        "expected_result": [
            FutureEntry(
                pair_id="BTC/USD",
                price=2664490000000,
                timestamp=1695293953,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=73224927992200000700416,
                expiry_timestamp=1695369600000,
                autoscale_volume=False,
            ),
            FutureEntry(
                pair_id="BTC/USD",
                price=2666120000000,
                timestamp=1695293953,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=271979672734799985901568,
                expiry_timestamp=1695974400000,
                autoscale_volume=False,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159390000000,
                timestamp=1695293986,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=36278392896900000907264,
                expiry_timestamp=1695369600000,
                autoscale_volume=False,
            ),
            FutureEntry(
                pair_id="ETH/USD",
                price=159092000000,
                timestamp=1695293987,
                source="OKX",
                publisher=PUBLISHER_NAME,
                volume=98295299247559996866560,
                expiry_timestamp=1695974400000,
                autoscale_volume=False,
            ),
        ],
    },
}

ONCHAIN_FETCHER_CONFIGS = {
    "GeckoTerminalFetcher": {
        "mock_file": MOCK_DIR / "responses" / "gecko.json",
        "fetcher_class": GeckoTerminalFetcher,
        "name": "GeckoTerminal",
        "expected_result": [
            SpotEntry(
                "R/USD",
                98898157,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=1264558.5626824791626951720608214185,
            ),
            SpotEntry(
                "WBTC/USD",
                2580468000000,
                12345,
                "GECKOTERMINAL",
                PUBLISHER_NAME,
                volume=90241580.528001091809493184,
            ),
        ],
    },
}

# %% SPOT


@pytest.fixture(params=FETCHER_CONFIGS.values())
def fetcher_config(request):
    return request.param


@pytest.fixture
def mock_data(fetcher_config):
    with open(fetcher_config["mock_file"], "r") as f:
        return json.load(f)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_fetcher(fetcher_config, mock_data):
    with aioresponses() as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=200, payload=mock_data[quote_asset])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)
        assert result == fetcher_config["expected_result"]


@pytest.mark.asyncio
async def test_async_fetcher_404_error(fetcher_config):
    with aioresponses() as mock:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=404)

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
    with requests_mock.Mocker() as m:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        # Mocking the expected call for assets
        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, json=mock_data[quote_asset])

        result = fetcher.fetch_sync()

        assert result == fetcher_config["expected_result"]


def test_fetcher_sync_404(fetcher_config):
    with requests_mock.Mocker() as m:
        fetcher = fetcher_config["fetcher_class"](SAMPLE_ASSETS, PUBLISHER_NAME)

        for asset in SAMPLE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, status_code=404)

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
def mock_future_data(future_fetcher_config):
    with open(future_fetcher_config["mock_file"], "r") as f:
        return json.load(f)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_future_fetcher(future_fetcher_config, mock_future_data):
    with aioresponses() as mock:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        other_mock_fns = future_fetcher_config.get("other_mock_fns", {})

        # Mocking the expected call for assets
        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            mock.get(url, status=200, payload=mock_future_data[quote_asset])

            # fetchers such as OkxFutureFetcher and BinanceFutureFetcher
            # have other API endpoints that must be mocked
            if other_mock_fns:
                for mock_fn in other_mock_fns:
                    [*fn], [*val] = zip(*mock_fn.items())
                    fn, val = fn[0], val[0]
                    url = getattr(fetcher, fn)(**val["kwargs"][quote_asset])
                    with open(val["mock_file"], "r") as f:
                        mock_file = json.load(f)
                    mock.get(url, status=200, payload=mock_file[quote_asset])

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
def test_future_fetcher_sync_success(future_fetcher_config, mock_future_data):
    with requests_mock.Mocker() as m:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        other_mock_fns = future_fetcher_config.get("other_mock_fns", {})

        # Mocking the expected call for assets
        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, json=mock_future_data[quote_asset])

            # fetchers such as OkxFutureFetcher and BinanceFutureFetcher
            # have other API endpoints that must be mocked
            if other_mock_fns:
                for mock_fn in other_mock_fns:
                    [*fn], [*val] = zip(*mock_fn.items())
                    fn, val = fn[0], val[0]
                    url = getattr(fetcher, fn)(**val["kwargs"][quote_asset])
                    with open(val["mock_file"], "r") as f:
                        mock_file = json.load(f)
                    m.get(url, json=mock_file[quote_asset])

        result = fetcher.fetch_sync()

        assert result == future_fetcher_config["expected_result"]


def test_future_fetcher_sync_404(future_fetcher_config):
    with requests_mock.Mocker() as m:
        fetcher = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME
        )

        for asset in SAMPLE_FUTURE_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, status_code=404)

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
    with open(onchain_fetcher_config["mock_file"], "r") as f:
        return json.load(f)


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
    with requests_mock.Mocker() as m:
        fetcher = onchain_fetcher_config["fetcher_class"](
            SAMPLE_ONCHAIN_ASSETS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in SAMPLE_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, json=onchain_mock_data[quote_asset])

        result = fetcher.fetch_sync()

        assert result == onchain_fetcher_config["expected_result"]


def test_onchain_fetcher_sync_404(onchain_fetcher_config):
    with requests_mock.Mocker() as m:
        fetcher = onchain_fetcher_config["fetcher_class"](
            SAMPLE_ONCHAIN_ASSETS, PUBLISHER_NAME
        )

        for asset in SAMPLE_ONCHAIN_ASSETS:
            quote_asset = asset["pair"][0]
            base_asset = asset["pair"][1]
            url = fetcher.format_url(quote_asset, base_asset)
            m.get(url, status_code=404)

        result = fetcher.fetch_sync()

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset['pair'][0]}/{asset['pair'][1]} from {onchain_fetcher_config['name']}"
            )
            for asset in SAMPLE_ONCHAIN_ASSETS
        ]

        assert result == expected_result
