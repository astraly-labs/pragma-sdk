import aiohttp
import pytest
import unittest

from unittest import mock
from aioresponses import aioresponses

from pragma_sdk.common.exceptions import PublisherFetchError
from tests.integration.constants import (
    SAMPLE_PAIRS,
    STABLE_MOCK_PRICE,
)
from tests.integration.fetchers.fetcher_configs import (
    PUBLISHER_NAME,
)
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from tests.integration.utils import are_entries_list_equal


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_rpc_fetcher(rpc_fetcher_config, mock_data):
    fetcher: FetcherInterfaceT = rpc_fetcher_config["fetcher_class"](
        SAMPLE_PAIRS, PUBLISHER_NAME
    )
    # Mocking the expected call for pair
    for pair in SAMPLE_PAIRS:
        base_asset = pair.base_currency

        # Mock when hopping is done
        if fetcher.hop_handler is not None:
            pair = fetcher.hop_handler.get_hop_pair(pair)

        url = fetcher.format_url(pair=pair)
        mock.get(url, status=200, payload=mock_data[base_asset.id])

    with unittest.mock.patch.object(
        fetcher.client, "get_spot", return_value=STABLE_MOCK_PRICE
    ):
        result = await fetcher.fetch(mock.MagicMock())
        assert are_entries_list_equal(result, rpc_fetcher_config["expected_result"])


@pytest.mark.asyncio
async def test_async_rpc_fetcher_404_error(rpc_fetcher_config):
    with aioresponses() as mock:
        fetcher: FetcherInterfaceT = rpc_fetcher_config["fetcher_class"](
            SAMPLE_PAIRS, PUBLISHER_NAME
        )

        for pair in SAMPLE_PAIRS:
            # Mock when hopping is done
            if fetcher.hop_handler is not None:
                pair = fetcher.hop_handler.get_hop_pair(pair)

            url = fetcher.format_url(pair=pair)
            mock.get(url, status=404)

        async with aiohttp.ClientSession() as session:
            with unittest.mock.patch.object(
                fetcher.client, "get_spot", return_value=STABLE_MOCK_PRICE
            ):
                result = await fetcher.fetch(session)
                # Adjust the expected result to reflect the 404 error
                expected_result = [
                    PublisherFetchError(
                        f"No data found for {pair} from {rpc_fetcher_config['name']}"
                    )
                    for pair in SAMPLE_PAIRS
                ]
                assert result == expected_result
