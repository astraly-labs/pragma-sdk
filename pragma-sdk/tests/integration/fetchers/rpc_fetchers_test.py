import pytest

from unittest import mock

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
