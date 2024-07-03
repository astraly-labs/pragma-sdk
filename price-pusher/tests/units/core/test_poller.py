import pytest
import logging
from unittest.mock import MagicMock, AsyncMock, patch
from price_pusher.core.poller import PricePoller
from pragma.common.types.entry import SpotEntry
from pragma.common.fetchers.fetcher_client import FetcherClient



@pytest.fixture
def fetcher_client():
    return MagicMock(spec=FetcherClient)


@pytest.fixture
def price_poller(fetcher_client):
    return PricePoller(fetcher_client=fetcher_client)


def test_set_update_prices_callback(price_poller):
    mock_callback = MagicMock()
    price_poller.set_update_prices_callback(mock_callback)
    assert price_poller.update_prices_callback == mock_callback


def test_is_requesting_onchain(fetcher_client):
    fetcher = MagicMock()
    fetcher.client.full_node_client = "something"
    fetcher_client.fetchers = [fetcher]
    poller = PricePoller(fetcher_client)
    assert poller._is_requesting_onchain is True

    fetcher.client.full_node_client = None
    fetcher_client.fetchers = [fetcher]
    poller = PricePoller(fetcher_client)
    assert poller._is_requesting_onchain is False


@pytest.mark.asyncio
async def test_poll_prices_no_callback(price_poller):
    with pytest.raises(ValueError, match="Update callback must be set."):
        await price_poller.poll_prices()


@pytest.mark.asyncio
async def test_poll_prices_success(price_poller, fetcher_client, caplog):
    caplog.set_level(logging.INFO)
    mock_callback = MagicMock()
    price_poller.set_update_prices_callback(mock_callback)

    dummy_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1234567890,
        source="source_1",
        publisher="publisher_1",
    )

    fetcher_client.fetch = AsyncMock(return_value=[dummy_entry])

    await price_poller.poll_prices()

    fetcher_client.fetch.assert_awaited_once()
    mock_callback.assert_called_once_with([dummy_entry])

    assert "POLLER successfully fetched 1 new entries!" in caplog.text


@pytest.mark.asyncio
async def test_poll_prices_failure(price_poller, fetcher_client, caplog):
    mock_callback = MagicMock()
    price_poller.set_update_prices_callback(mock_callback)

    fetcher_client.fetch = AsyncMock(side_effect=Exception("Fetch failed"))

    with pytest.raises(Exception, match="Fetch failed"):
        await price_poller.poll_prices()

    fetcher_client.fetch.assert_awaited_once()
    mock_callback.assert_not_called()


@pytest.mark.asyncio
async def test_poll_prices_retry_success(price_poller, fetcher_client, caplog):
    caplog.set_level(logging.INFO)
    mock_callback = MagicMock()
    price_poller.set_update_prices_callback(mock_callback)

    dummy_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1234567890,
        source="source_1",
        publisher="publisher_1",
    )

    fetcher_client.fetchers = [MagicMock()]
    price_poller._is_requesting_onchain = True
    fetcher_client.fetch = AsyncMock(side_effect=[Exception("Fetch failed"), [dummy_entry]])

    retry_async_mock = AsyncMock(return_value=[dummy_entry])
    with patch("price_pusher.utils.retries.retry_async", new=retry_async_mock):
        await price_poller.poll_prices()

    assert fetcher_client.fetch.await_count == 2
    mock_callback.assert_called_once_with([dummy_entry])

    assert "🤔 POLLER fetching prices failed. Retrying..." in caplog.text
    assert "🙏 Retry successfull!" in caplog.text


@pytest.mark.asyncio
async def test_poll_prices_retry_failure(price_poller, fetcher_client, caplog):
    mock_callback = MagicMock()
    price_poller.set_update_prices_callback(mock_callback)

    fetcher_client.fetchers = [MagicMock()]
    price_poller._is_requesting_onchain = True
    fetcher_client.fetch = AsyncMock(side_effect=Exception("Fetch failed"))

    retry_async = AsyncMock(side_effect=Exception("Retry failed"))

    with patch("price_pusher.core.poller.retry_async", new=retry_async):
        with pytest.raises(
            ValueError,
            match="POLLERS retries for fetching new prices still failed: Retry failed",
        ):
            await price_poller.poll_prices()

    fetcher_client.fetch.assert_awaited_once()
    retry_async.assert_awaited_once()
    mock_callback.assert_not_called()

    assert "🤔 POLLER fetching prices failed. Retrying..." in caplog.text
