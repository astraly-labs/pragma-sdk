import json

import aiohttp
import pytest
from aioresponses import aioresponses

from pragma.core.entry import SpotEntry
from pragma.publisher.assets import PRAGMA_ALL_ASSETS
from pragma.publisher.fetchers import CexFetcher
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
