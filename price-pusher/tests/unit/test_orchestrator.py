import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from tests.constants import BTC_USD_PAIR

from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.types.entry import Entry, SpotEntry, FutureEntry

from price_pusher.core.poller import PricePoller
from price_pusher.core.listener import PriceListener
from price_pusher.core.pusher import PricePusher
from price_pusher.orchestrator import Orchestrator


@pytest.fixture
def mock_poller():
    return AsyncMock(spec=PricePoller)


@pytest.fixture
def mock_listener():
    listener = MagicMock(spec=PriceListener)
    listener.notification_event = MagicMock()
    listener.notification_event.wait = AsyncMock()
    listener.notification_event.is_set = MagicMock(side_effect=[True, False])
    listener.price_config = MagicMock()
    listener.price_config.get_all_assets.return_value = {
        DataTypes.SPOT: [BTC_USD_PAIR],
    }
    listener.id = "listener_1"
    return listener


@pytest.fixture
def mock_pusher():
    return AsyncMock(spec=PricePusher)


@pytest.fixture
def orchestrator(mock_poller, mock_listener, mock_pusher):
    return Orchestrator(poller=mock_poller, listeners=[mock_listener], pusher=mock_pusher)


@pytest.mark.asyncio
async def test_run_forever(orchestrator):
    orchestrator._poller_service = AsyncMock()
    orchestrator._listener_services = AsyncMock()
    orchestrator._pusher_service = AsyncMock()

    run_forever_task = asyncio.create_task(orchestrator.run_forever())
    await asyncio.sleep(2)
    run_forever_task.cancel()

    orchestrator._poller_service.assert_called_once()
    orchestrator._listener_services.assert_called_once()
    orchestrator._pusher_service.assert_called_once()


@pytest.mark.asyncio
async def test_poller_service(orchestrator, mock_poller):
    orchestrator._poller_service_task = asyncio.create_task(orchestrator._poller_service())
    await asyncio.sleep(1)
    assert mock_poller.poll_prices.call_count > 0
    orchestrator._poller_service_task.cancel()


@pytest.mark.asyncio
async def test_listener_services(orchestrator, mock_listener):
    orchestrator._start_listener = AsyncMock()
    listener_services_task = asyncio.create_task(orchestrator._listener_services())
    await asyncio.sleep(1)
    listener_services_task.cancel()
    orchestrator._start_listener.assert_called_with(mock_listener)


@pytest.mark.asyncio
async def test_start_listener(orchestrator, mock_listener):
    orchestrator._handle_listener = AsyncMock()
    start_listener_task = asyncio.create_task(orchestrator._start_listener(mock_listener))
    await asyncio.sleep(1)
    start_listener_task.cancel()
    orchestrator._handle_listener.assert_called_with(mock_listener)
    mock_listener.run_forever.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_listener(orchestrator, mock_listener, caplog):
    caplog.set_level(logging.INFO)

    # Create mock entries and set their get_pair_id method return value
    mock_entry = MagicMock(spec=Entry)
    mock_entry.get_pair_id.return_value = "BTC/USD"

    # Mock _flush_entries_for_assets method
    orchestrator._flush_entries_for_assets = MagicMock(return_value=[mock_entry])

    # Set up the mock behavior
    mock_listener.notification_event.wait.side_effect = [None, asyncio.CancelledError()]

    # Run the _handle_listener method
    handle_listener_task = asyncio.create_task(orchestrator._handle_listener(mock_listener))

    # Let the task run for a bit
    await asyncio.sleep(1)

    # Cancel the task
    handle_listener_task.cancel()
    try:
        await handle_listener_task
    except asyncio.CancelledError:
        pass

    # Assertions
    mock_listener.notification_event.clear.assert_called_once()
    mock_listener.price_config.get_all_assets.assert_called_once()

    # Check logs
    assert any(
        "💡 Notification received from LISTENER" in record.message for record in caplog.records
    )

    # Check if the correct entries were pushed to the queue
    assert orchestrator.push_queue.qsize() == 1
    entries_to_push = await orchestrator.push_queue.get()
    assert len(entries_to_push) == 1  # Ensure there's one entry pushed

    # Check the queue contains the correct entries
    expected_asset_id = mock_listener.price_config.get_all_assets.return_value[DataTypes.SPOT][
        0
    ].__repr__()
    for entry in entries_to_push:
        assert entry.get_pair_id() == expected_asset_id


@pytest.mark.asyncio
async def test_pusher_service(orchestrator, mock_pusher):
    entries = [MagicMock(spec=Entry)]
    await orchestrator.push_queue.put(entries)
    pusher_service_task = asyncio.create_task(orchestrator._pusher_service())
    await asyncio.sleep(1)
    assert mock_pusher.update_price_feeds.call_count > 0
    pusher_service_task.cancel()


def test_callback_update_prices(orchestrator):
    spot_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1234567890,
        source="source_1",
        publisher="publisher_1",
    )

    future_entry = FutureEntry(
        pair_id="ETH/USD",
        price=500,
        timestamp=1234567890,
        source="source_2",
        publisher="publisher_2",
        expiry_timestamp=1234569999,
    )

    orchestrator.callback_update_prices([spot_entry, future_entry])

    assert "BTC/USD" in orchestrator.latest_prices
    assert "ETH/USD" in orchestrator.latest_prices
    assert DataTypes.SPOT in orchestrator.latest_prices["BTC/USD"]
    assert DataTypes.FUTURE in orchestrator.latest_prices["ETH/USD"]


def test_flush_entries_for_assets(orchestrator):
    pair = BTC_USD_PAIR
    pair_id = pair.__repr__()

    spot_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1234567890,
        source="source_1",
        publisher="publisher_1",
    )

    future_entry = FutureEntry(
        pair_id="BTC/USD",
        price=500,
        timestamp=1234567890,
        source="source_2",
        publisher="publisher_2",
        expiry_timestamp=1234569999,
    )

    orchestrator.latest_prices[pair_id] = {
        DataTypes.SPOT: {"source_1": spot_entry},
        DataTypes.FUTURE: {"source_2": future_entry},
    }

    entries = orchestrator._flush_entries_for_assets(
        {DataTypes.SPOT: [pair], DataTypes.FUTURE: [pair]}
    )
    assert spot_entry in entries
    assert future_entry in entries
    assert DataTypes.SPOT not in orchestrator.latest_prices[pair_id]
    assert DataTypes.FUTURE not in orchestrator.latest_prices[pair_id]
