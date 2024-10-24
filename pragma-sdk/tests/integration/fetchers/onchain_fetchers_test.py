from unittest import mock

import aiohttp
import pytest
from aioresponses import aioresponses

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.exceptions import PublisherFetchError

from tests.integration.fixtures.fetchers import get_mock_data
from tests.integration.fetchers.fetcher_configs import (
    PUBLISHER_NAME,
)
from tests.integration.constants import ONCHAIN_SAMPLE_PAIRS
from tests.integration.utils import are_entries_list_equal


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_onchain_async_fetcher(onchain_fetcher_config):
    mock_data = get_mock_data(onchain_fetcher_config)
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = onchain_fetcher_config["fetcher_class"](
            ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME
        )

        # Mocking the expected call for assets
        for pair in ONCHAIN_SAMPLE_PAIRS:
            base_asset = pair.base_currency
            if fetcher.hop_handler:
                pair = fetcher.hop_handler.get_hop_pair(pair)
            url = fetcher.format_url(pair)
            mock.get(url, status=200, payload=mock_data[base_asset.id])

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        assert are_entries_list_equal(result, onchain_fetcher_config["expected_result"])


@pytest.mark.asyncio
async def test_onchain_async_fetcher_404_error(onchain_fetcher_config):
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = onchain_fetcher_config["fetcher_class"](
            ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME
        )

        for pair in ONCHAIN_SAMPLE_PAIRS:
            if fetcher.hop_handler:
                pair = fetcher.hop_handler.get_hop_pair(pair)
            url = fetcher.format_url(pair)
            mock.get(url, status=404)
            if onchain_fetcher_config["name"] == "Dexscreener":
                inverse_pair = Pair.from_tickers(
                    pair.quote_currency.id, pair.base_currency.id
                )
                url = fetcher.format_url(inverse_pair)
                mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

        # Adjust the expected result to reflect the 404 error
        expected_message = "No data found"
        for res in result:
            assert isinstance(res, PublisherFetchError)
            assert expected_message in res.message
