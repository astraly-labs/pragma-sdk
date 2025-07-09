import pytest
import logging
import asyncio

from unittest.mock import MagicMock, AsyncMock, patch
from price_pusher.core.listener import PriceListener
from price_pusher.configs import PriceConfig
from price_pusher.core.request_handlers.interface import IRequestHandler

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.types import DataTypes

from tests.constants import BTC_USD_PAIR

PUBLISHER = "PUBLISHER_1"
SOURCE_1 = "SOURCE_1"
SOURCE_2 = "SOURCE_2"
SOURCE_3 = "SOURCE_3"
SOURCE_4 = "SOURCE_4"


@pytest.fixture
def mock_request_handler():
    return AsyncMock(spec=IRequestHandler)


@pytest.fixture
def mock_price_config():
    config = MagicMock(spec=PriceConfig)
    config.price_deviation = 0.1
    config.time_difference = 60
    config.get_all_assets.return_value = {DataTypes.SPOT: [BTC_USD_PAIR]}
    return config


@pytest.fixture
def price_listener(mock_request_handler, mock_price_config):
    return PriceListener(
        request_handler=mock_request_handler,
        price_config=mock_price_config,
        polling_frequency_in_s=10,
    )


@pytest.mark.asyncio
async def test_run_forever(price_listener):
    with (
        patch.object(price_listener, "_fetch_all_oracle_prices", AsyncMock()),
        patch.object(
            price_listener, "_does_oracle_needs_update", AsyncMock(return_value=True)
        ),
        patch.object(price_listener, "_notify", MagicMock()),
    ):
        price_listener._fetch_all_oracle_prices.side_effect = lambda: asyncio.sleep(0.1)
        task = asyncio.create_task(price_listener.run_forever())

        await asyncio.sleep(0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        price_listener._fetch_all_oracle_prices.assert_called()
        price_listener._does_oracle_needs_update.assert_called()
        price_listener._notify.assert_called()


def test_set_orchestrator_prices(price_listener):
    orchestrator_prices = {"BTC/USD": {DataTypes.SPOT: MagicMock(spec=Entry)}}
    price_listener.set_orchestrator_prices(orchestrator_prices)
    assert price_listener.orchestrator_prices == orchestrator_prices


@pytest.mark.asyncio
async def test_fetch_all_oracle_prices(
    price_listener, mock_request_handler, mock_price_config
):
    mock_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1234567890,
        source="ONCHAIN",
        publisher="AGGREGATION",
    )
    mock_request_handler.fetch_latest_entries.return_value = mock_entry

    price_listener.orchestrator_prices = {
        "BTC/USD": {DataTypes.SPOT: {SOURCE_1: mock_entry}}
    }

    await price_listener._fetch_all_oracle_prices()

    data_type = list(mock_price_config.get_all_assets.return_value.keys())[0]
    pair = mock_price_config.get_all_assets.return_value[data_type][0]

    mock_request_handler.fetch_latest_entries.assert_called_once_with(
        pair=pair, data_type=data_type, sources=[SOURCE_1]
    )
    assert "BTC/USD" in price_listener.oracle_prices
    assert DataTypes.SPOT in price_listener.oracle_prices["BTC/USD"]
    assert price_listener.oracle_prices["BTC/USD"][DataTypes.SPOT] == mock_entry


def test_get_most_recent_orchestrator_entry(price_listener):
    mock_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1234567890,
        source=SOURCE_1,
        publisher=PUBLISHER,
    )
    mock_entry.base.timestamp = 1000
    price_listener.orchestrator_prices = {
        "BTC/USD": {DataTypes.SPOT: {SOURCE_1: mock_entry}}
    }

    result = price_listener._get_latest_orchestrator_entry("BTC/USD", DataTypes.SPOT)
    assert result == mock_entry


@pytest.mark.asyncio
async def test_oracle_needs_update_because_outdated(caplog, price_listener):
    caplog.set_level(logging.INFO)
    orchestrator_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1000000061,
        source=SOURCE_1,
        publisher=PUBLISHER,
    )
    oracle_entry = SpotEntry(
        pair_id="BTC/USD",
        price=10000,
        timestamp=1000000000,
        source="AGGREGATION",
        publisher="ORACLE",
    )
    price_listener.orchestrator_prices = {
        "BTC/USD": {DataTypes.SPOT: {SOURCE_1: orchestrator_entry}}
    }
    price_listener.oracle_prices = {"BTC/USD": {DataTypes.SPOT: oracle_entry}}
    assert await price_listener._does_oracle_needs_update()
    assert "is too old" in caplog.text


@pytest.mark.asyncio
async def test_oracle_needs_update_because_deviating(caplog, price_listener):
    caplog.set_level(logging.INFO)
    orchestrator_entry = SpotEntry(
        pair_id="BTC/USD",
        price=111,
        timestamp=1000000000,
        source=SOURCE_1,
        publisher=PUBLISHER,
    )
    oracle_entry = SpotEntry(
        pair_id="BTC/USD",
        price=100,
        timestamp=1000000000,
        source="AGGREGATION",
        publisher="ORACLE",
    )
    price_listener.orchestrator_prices = {
        "BTC/USD": {DataTypes.SPOT: {SOURCE_1: orchestrator_entry}}
    }
    price_listener.oracle_prices = {"BTC/USD": {DataTypes.SPOT: oracle_entry}}
    assert await price_listener._does_oracle_needs_update()
    assert "is deviating from the config bounds" in caplog.text


def test_new_price_is_deviating(price_listener):
    # Config is deviation = 0.1 / 10%
    assert price_listener._new_price_is_deviating(
        pair_id="BTC/USD", new_price=111, oracle_price=100
    )


def test_oracle_entry_is_outdated(price_listener):
    # Config max delta seconds is 60
    mock_oracle_entry = MagicMock(spec=SpotEntry)
    mock_oracle_entry.get_timestamp.return_value = 1000
    mock_newest_entry = MagicMock(spec=SpotEntry)
    mock_newest_entry.get_timestamp.return_value = 1061
    assert price_listener._oracle_entry_is_outdated(
        "BTC/USD", mock_oracle_entry, mock_newest_entry
    )


def test_notify(caplog, price_listener):
    caplog.set_level(logging.INFO)
    with patch.object(
        price_listener.notification_event, "set", MagicMock()
    ) as mock_set:
        price_listener._notify()
        mock_set.assert_called_once()
        assert "sending notification to the Orchestrator!" in caplog.text


def test_log_listener_spawning(caplog, price_listener, mock_price_config):
    caplog.set_level(logging.INFO)
    price_listener._log_listener_spawning()
    assert "👂 Spawned listener [" in caplog.text


def test_get_sources_for_pair(price_listener):
    orchestrator_entry = SpotEntry(
        pair_id="BTC/USD",
        price=111,
        timestamp=1000000000,
        source=SOURCE_1,
        publisher=PUBLISHER,
    )

    price_listener.orchestrator_prices = {
        "BTC/USD": {
            DataTypes.SPOT: {
                SOURCE_1: orchestrator_entry,
                SOURCE_3: orchestrator_entry,
            },
            DataTypes.FUTURE: {
                SOURCE_1: {0: orchestrator_entry},
                SOURCE_2: {0: orchestrator_entry},
                SOURCE_4: {0: orchestrator_entry},
            },
        }
    }

    spot_sources = price_listener._get_sources_for_pair(BTC_USD_PAIR, DataTypes.SPOT)
    assert spot_sources == [SOURCE_1, SOURCE_3]

    future_sources = price_listener._get_sources_for_pair(
        BTC_USD_PAIR, DataTypes.FUTURE
    )
    assert future_sources == [SOURCE_1, SOURCE_2, SOURCE_4]
