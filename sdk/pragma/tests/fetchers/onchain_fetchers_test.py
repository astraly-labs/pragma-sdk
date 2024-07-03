from unittest import mock

import aiohttp
import pytest
from aioresponses import aioresponses

from pragma.common.exceptions import PublisherFetchError
from pragma.tests.fetchers.fetcher_configs import (
    PUBLISHER_NAME,
)
from pragma.tests.constants import ONCHAIN_SAMPLE_PAIRS
from pragma.common.fetchers.interface import FetcherInterfaceT


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_onchain_async_fetcher(onchain_fetcher_config, onchain_mock_data):
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = onchain_fetcher_config["fetcher_class"](
            ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in ONCHAIN_SAMPLE_PAIRS:
            base_asset = asset.base_currency
            url = fetcher.format_url(asset)
            mock.get(url, status=200, payload=onchain_mock_data[base_asset.id])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)
        assert result == onchain_fetcher_config["expected_result"]


@pytest.mark.asyncio
async def test_onchain_async_fetcher_404_error(onchain_fetcher_config):
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = onchain_fetcher_config["fetcher_class"](
            ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME
        )

        for asset in ONCHAIN_SAMPLE_PAIRS:
            url = fetcher.format_url(asset)
            mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset} from {onchain_fetcher_config['name']}"
            )
            for asset in ONCHAIN_SAMPLE_PAIRS
        ]

        assert result == expected_result
