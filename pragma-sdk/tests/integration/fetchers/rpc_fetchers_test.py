import pytest

from unittest import mock

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError

from tests.integration.fixtures.fetchers import get_mock_data
from tests.integration.constants import (
    ONCHAIN_SAMPLE_PAIRS,
    STABLE_MOCK_PRICE,
)
from tests.integration.fetchers.fetcher_configs import (
    PUBLISHER_NAME,
)
from tests.integration.utils import are_entries_list_equal


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_async_rpc_fetcher(rpc_fetcher_config):
    mock_data = get_mock_data(rpc_fetcher_config)
    fetcher = rpc_fetcher_config["fetcher_class"](ONCHAIN_SAMPLE_PAIRS, PUBLISHER_NAME)

    with (
        mock.patch.object(
            fetcher.client,
            "get_spot",
            return_value=STABLE_MOCK_PRICE,
        ),
        mock.patch.object(
            fetcher.client.full_node_client,
            "call_contract",
            side_effect=list(mock_data.values()),
        ),
    ):
        result = await fetcher.fetch(session=mock.MagicMock())
        assert are_entries_list_equal(result, rpc_fetcher_config["expected_result"])


# NOTE: This test work because we only have Ekubo as Rpc Fetcher for now.
# NOTE: If you just added a new fetcher here and this fail, adapt/remove this test.
@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_publisher_error_async_rpc_fetcher(rpc_fetcher_config):
    pairs = [Pair.from_tickers("SOL", "USD")]
    fetcher = rpc_fetcher_config["fetcher_class"](pairs, PUBLISHER_NAME)

    with (
        mock.patch.object(
            fetcher.client,
            "get_spot",
            return_value=STABLE_MOCK_PRICE,
        ),
        mock.patch.object(
            fetcher.client.full_node_client,
            "call_contract",
            return_value=[1, 0],
        ),
    ):
        result = await fetcher.fetch(session=mock.MagicMock())
        expected = [
            PublisherFetchError("Price feed not initialized for SOL/USDC in Ekubo")
        ]
        assert result == expected
