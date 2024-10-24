from unittest import mock

import aiohttp
import pytest
from aioresponses import aioresponses

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from tests.integration.fixtures.fetchers import get_mock_data
from tests.integration.constants import (
    SAMPLE_FUTURE_PAIRS,
)
from tests.integration.fetchers.fetcher_configs import (
    PUBLISHER_NAME,
)
from tests.integration.utils import are_entries_list_equal


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_future_fetcher(future_fetcher_config, other_mock_endpoints):
    mock_data = get_mock_data(future_fetcher_config)
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_PAIRS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for asset in SAMPLE_FUTURE_PAIRS:
            base_asset = asset.base_currency
            url = fetcher.format_url(asset)
            mock.get(url, status=200, payload=mock_data[base_asset.id])

        if other_mock_endpoints:
            for endpoint in other_mock_endpoints:
                mock.get(endpoint["url"], status=200, payload=endpoint["json"])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        assert are_entries_list_equal(result, future_fetcher_config["expected_result"])


@pytest.mark.asyncio
async def test_async_future_fetcher_404_error(future_fetcher_config):
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = future_fetcher_config["fetcher_class"](
            SAMPLE_FUTURE_PAIRS, PUBLISHER_NAME
        )

        for asset in SAMPLE_FUTURE_PAIRS:
            url = fetcher.format_url(asset)
            mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_result = [
            PublisherFetchError(
                f"No data found for {asset} from {future_fetcher_config['name']}"
            )
            for asset in SAMPLE_FUTURE_PAIRS
        ]

        assert result == expected_result
