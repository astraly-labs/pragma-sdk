import pytest

from unittest.mock import MagicMock, patch

from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.common.types.entry import GenericEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.generic_fetchers.deribit.fetcher import DeribitOptionsFetcher

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.constants import DERIBIT_MERKLE_FEED_KEY

from merkle_maker.redis import RedisManager
from merkle_maker.main import main


@pytest.mark.asyncio
async def test_main():
    mock_pragma_client = MagicMock(spec=PragmaOnChainClient)
    mock_redis_manager = MagicMock(spec=RedisManager)
    mock_fetcher_client = MagicMock(spec=FetcherClient)
    mock_deribit_fetcher = MagicMock(spec=DeribitOptionsFetcher)

    # Set up mock return values
    mock_pragma_client.get_block_number.side_effect = [
        100,
        101,
        102,
    ]
    mock_fetcher_client.fetch.return_value = [
        GenericEntry(
            key=DERIBIT_MERKLE_FEED_KEY,
            value=420694206942069,
            timestamp=1,
            source=str_to_felt("DERIBIT"),
            publisher=str_to_felt("TEST_PUBLISHER"),
        )
    ]
    mock_pragma_client.publish_entries.return_value = None

    with (
        patch(
            "merkle_maker.main.PragmaOnChainClient", return_value=mock_pragma_client
        ) as mock_pragma_client_class,
        patch(
            "merkle_maker.main.RedisManager", return_value=mock_redis_manager
        ) as mock_redis_manager_class,
        patch(
            "merkle_maker.main.FetcherClient", return_value=mock_fetcher_client
        ) as mock_fetcher_client_class,
        patch(
            "merkle_maker.main.DeribitOptionsFetcher", return_value=mock_deribit_fetcher
        ) as mock_deribit_fetcher_class,
        patch("merkle_maker.main._publish_merkle_feeds_forever") as mock_publish_forever,
    ):
        # Call the main function
        await main(
            network="sepolia",
            redis_host="localhost:6379",
            publisher_name="TEST_PUBLISHER",
            publisher_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890",
            block_interval=1,
        )

        # Assert that the necessary objects were created
        mock_pragma_client_class.assert_called_once_with(
            chain_name="sepolia",
            network="sepolia",
            account_contract_address="0x1234567890123456789012345678901234567890",
            account_private_key="0x1234567890123456789012345678901234567890",
        )
        mock_redis_manager_class.assert_called_once_with(host="localhost", port="6379")
        mock_fetcher_client_class.assert_called_once()
        mock_deribit_fetcher_class.assert_called_once_with(
            pairs=[
                Pair.from_tickers("BTC", "USD"),
                Pair.from_tickers("ETH", "USD"),
            ],
            publisher="TEST_PUBLISHER",
        )

        # Assert that the fetcher was added to the fetcher client
        mock_fetcher_client.add_fetcher.assert_called_once_with(mock_deribit_fetcher)

        # Assert that _publish_merkle_feeds_forever was called with the correct arguments
        mock_publish_forever.assert_called_once_with(
            network="sepolia",
            pragma_client=mock_pragma_client,
            fetcher_client=mock_fetcher_client,
            redis_manager=mock_redis_manager,
            block_interval=1,
        )
