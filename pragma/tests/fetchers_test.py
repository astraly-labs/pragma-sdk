import json

import aiohttp
import pytest
import requests_mock
from aioresponses import aioresponses

from pragma.core.entry import SpotEntry
from pragma.publisher.assets import PRAGMA_ALL_ASSETS
from pragma.publisher.fetchers import CexFetcher
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import MOCK_DIR

SAMPLE_ASSETS = [
    {"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "USD"), "decimals": 8},
]
PUBLISHER_NAME = "TEST_PUBLISHER"


@pytest.mark.asyncio
async def test_cex_fetcher():
    with open(MOCK_DIR / "responses" / "cex.json", "r") as f:
        mock_data = json.load(f)

    with aioresponses() as mock:
        # Mocking the expected call for BTC/USD
        mock.get(
            "https://cex.io/api/ticker/BTC/USD", status=200, payload=mock_data["BTC"]
        )

        # Mocking the expected call for ETH/USD
        mock.get(
            "https://cex.io/api/ticker/ETH/USD", status=200, payload=mock_data["ETH"]
        )

        fetcher = CexFetcher(SAMPLE_ASSETS, PUBLISHER_NAME)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        expected_result = [
            SpotEntry("BTC/USD", 2601210000000, 1692717096, "CEX", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 163921000000, 1692724899, "CEX", PUBLISHER_NAME),
        ]

        assert result == expected_result


@pytest.mark.asyncio
async def test_cex_fetcher_404_error():
    with open(MOCK_DIR / "responses" / "cex.json", "r") as f:
        mock_data = json.load(f)

    with aioresponses() as mock:
        # Mocking a successful call for BTC/USD
        mock.get(
            "https://cex.io/api/ticker/BTC/USD", status=200, payload=mock_data["BTC"]
        )

        # Mocking a 404 error for ETH/USD
        mock.get("https://cex.io/api/ticker/ETH/USD", status=404)

        fetcher = CexFetcher(SAMPLE_ASSETS, PUBLISHER_NAME)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            SpotEntry("BTC/USD", 2601210000000, 1692717096, "CEX", PUBLISHER_NAME),
            PublisherFetchError("No data found for ETH/USD from CEX"),
        ]

        assert result == expected_result


def test_cex_fetcher_sync_success():
    with open(MOCK_DIR / "responses" / "cex.json", "r") as f:
        mock_data = json.load(f)

    with requests_mock.Mocker() as m:
        m.get("https://cex.io/api/ticker/BTC/USD", json=mock_data["BTC"])
        m.get("https://cex.io/api/ticker/ETH/USD", json=mock_data["ETH"])

        fetcher = CexFetcher(SAMPLE_ASSETS, PUBLISHER_NAME)
        result = fetcher.fetch_sync()

        expected_result = [
            SpotEntry("BTC/USD", 2601210000000, 1692717096, "CEX", PUBLISHER_NAME),
            SpotEntry("ETH/USD", 163921000000, 1692724899, "CEX", PUBLISHER_NAME),
        ]

        assert result == expected_result
