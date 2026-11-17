"""
A publisher sharing its feeds with others (a validator next to Pragma's
publishers) must decide to push from its own entries: the aggregated timestamp
stays fresh as long as anyone else publishes.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.utils import str_to_felt

from price_pusher.configs import PriceConfig
from price_pusher.core.listener import PriceListener
from price_pusher.core.request_handlers.publisher import (
    BulkPublisherRequestHandler,
    PublisherRequestHandler,
)

from tests.constants import BTC_USD_PAIR

STAKER = "0x077d4b4e7ae321aabd0a5a7322108635fcbd0cd746f9ae217b8ea00363494b65"


def _own(source: str, price: int, timestamp: int) -> SpotEntry:
    return SpotEntry("BTC/USD", price, timestamp, source, STAKER)


def _client(own: dict, allowed: list[str] | Exception = ("BINANCE", "OKX", "BYBIT")):
    async def get_entry(pair_id, data_type, publisher, source, block_id):
        assert publisher == int(STAKER, 16)
        if source not in own:
            raise Exception("Contract error: 'No data entry found'")
        value = own[source]
        if isinstance(value, Exception):
            raise value
        return value

    client = SimpleNamespace(get_entry=AsyncMock(side_effect=get_entry))
    if isinstance(allowed, Exception):
        client.get_publisher_sources = AsyncMock(side_effect=allowed)
    else:
        client.get_publisher_sources = AsyncMock(
            return_value=[str_to_felt(s) for s in allowed]
        )
    return client


@pytest.mark.asyncio
async def test_fresh_entries_give_median_and_oldest_timestamp():
    client = _client(
        {
            "BINANCE": _own("BINANCE", 100, 1_000),
            "OKX": _own("OKX", 102, 900),
            "BYBIT": _own("BYBIT", 104, 950),
        }
    )
    handler = PublisherRequestHandler(client, STAKER)

    (entry,) = await handler.fetch_latest_entries(
        BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE", "OKX", "BYBIT"]
    )

    assert entry.price == 102
    assert entry.get_timestamp() == 900
    assert entry.base.publisher == int(STAKER, 16)


@pytest.mark.asyncio
async def test_missing_whitelisted_source_counts_as_never_published():
    client = _client({"BINANCE": _own("BINANCE", 100, 1_000)})
    handler = PublisherRequestHandler(client, STAKER)

    (entry,) = await handler.fetch_latest_entries(
        BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE", "OKX"]
    )

    assert entry.get_timestamp() == 0


@pytest.mark.asyncio
async def test_source_not_whitelisted_is_ignored():
    client = _client({"BINANCE": _own("BINANCE", 100, 1_000)}, allowed=["BINANCE"])
    handler = PublisherRequestHandler(client, STAKER)

    (entry,) = await handler.fetch_latest_entries(
        BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE", "KRAKEN"]
    )

    assert entry.get_timestamp() == 1_000
    assert client.get_entry.await_count == 1


@pytest.mark.asyncio
async def test_nothing_published_yet_returns_no_entry():
    handler = PublisherRequestHandler(_client({}), STAKER)
    assert (
        await handler.fetch_latest_entries(BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE"])
        == []
    )


@pytest.mark.asyncio
async def test_rpc_error_is_not_mistaken_for_a_missing_entry():
    client = _client({"BINANCE": ConnectionError("node unreachable")})
    handler = PublisherRequestHandler(client, STAKER)
    with pytest.raises(ConnectionError):
        await handler.fetch_latest_entries(BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE"])


@pytest.mark.asyncio
async def test_unreadable_whitelist_counts_every_source():
    client = _client(
        {"BINANCE": _own("BINANCE", 100, 1_000)}, allowed=Exception("rpc down")
    )
    handler = PublisherRequestHandler(client, STAKER)

    (entry,) = await handler.fetch_latest_entries(
        BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE", "OKX"]
    )

    assert entry.get_timestamp() == 0


@pytest.mark.asyncio
async def test_whitelist_is_cached():
    client = _client({"BINANCE": _own("BINANCE", 100, 1_000)})
    handler = PublisherRequestHandler(client, STAKER)
    for _ in range(3):
        await handler.fetch_latest_entries(BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE"])
    assert client.get_publisher_sources.await_count == 1


@pytest.mark.asyncio
async def test_future_pairs_are_not_tracked():
    handler = PublisherRequestHandler(_client({}), STAKER)
    assert (
        await handler.fetch_latest_entries(BTC_USD_PAIR, DataTypes.FUTURE, ["BINANCE"])
        == []
    )


def _listener(handler) -> PriceListener:
    config = MagicMock(spec=PriceConfig)
    config.price_deviation = 0.01
    config.time_difference = 60
    config.get_all_assets.return_value = {DataTypes.SPOT: [BTC_USD_PAIR]}
    return PriceListener(
        request_handler=handler, price_config=config, polling_frequency_in_s=10
    )


def _poller_prices(timestamp: int, price: int = 100) -> dict:
    return {
        "BTC/USD": {
            DataTypes.SPOT: {
                source: SpotEntry("BTC/USD", price, timestamp, source, STAKER)
                for source in ("BINANCE", "OKX")
            }
        }
    }


@pytest.mark.asyncio
async def test_listener_pushes_when_own_source_is_missing():
    client = _client({"BINANCE": _own("BINANCE", 100, 1_000)})
    listener = _listener(PublisherRequestHandler(client, STAKER))
    listener.set_orchestrator_prices(_poller_prices(timestamp=1_010))

    await listener._fetch_all_oracle_prices()

    assert await listener._does_oracle_needs_update()


@pytest.mark.asyncio
async def test_listener_stays_quiet_when_own_entries_are_fresh():
    client = _client(
        {
            "BINANCE": _own("BINANCE", 100, 1_000),
            "OKX": _own("OKX", 100, 1_000),
        }
    )
    listener = _listener(PublisherRequestHandler(client, STAKER))
    listener.set_orchestrator_prices(_poller_prices(timestamp=1_010))

    await listener._fetch_all_oracle_prices()

    assert not await listener._does_oracle_needs_update()


def _bulk_client(entries: list[SpotEntry]):
    client = SimpleNamespace(get_spot_entries=AsyncMock(return_value=entries))
    client.get_publisher_sources = AsyncMock(
        return_value=[str_to_felt(s) for s in ("BINANCE", "OKX", "BYBIT")]
    )
    return client


@pytest.mark.asyncio
async def test_bulk_reads_own_entries_in_one_call():
    other = "0x0123"
    client = _bulk_client(
        [
            _own("BINANCE", 100, 1_000),
            _own("OKX", 102, 900),
            SpotEntry("BTC/USD", 500, 2_000, "OKX", other),
            SpotEntry("BTC/USD", 500, 2_000, "BYBIT", other),
        ]
    )
    handler = BulkPublisherRequestHandler(client, STAKER)

    (entry,) = await handler.fetch_latest_entries(
        BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE", "OKX"]
    )

    assert entry.price == 101
    assert entry.get_timestamp() == 900
    client.get_spot_entries.assert_awaited_once()


@pytest.mark.asyncio
async def test_bulk_source_only_published_by_others_counts_as_missing():
    client = _bulk_client(
        [
            _own("BINANCE", 100, 1_000),
            SpotEntry("BTC/USD", 500, 2_000, "OKX", "0x0123"),
        ]
    )
    handler = BulkPublisherRequestHandler(client, STAKER)

    (entry,) = await handler.fetch_latest_entries(
        BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE", "OKX"]
    )

    assert entry.price == 100
    assert entry.get_timestamp() == 0


@pytest.mark.asyncio
async def test_outvoted_push_does_not_retrigger():
    """
    2026-11-15: own entries fresh at 1775, others stale at 1743, aggregated
    median stuck at 1743. Against own entries there is nothing left to push.
    """
    own = [_own(s, 1775, 1_000) for s in ("BINANCE", "OKX", "BYBIT")]
    stale = [SpotEntry("BTC/USD", 1743, 400, s, "0x0123") for s in ("BINANCE", "OKX")]
    handler = BulkPublisherRequestHandler(_bulk_client(own + stale), STAKER)
    config = PriceConfig(
        pairs={"spot": ["BTC/USD"]}, time_difference=1800, price_deviation=0.01
    )
    listener = PriceListener(handler, config, polling_frequency_in_s=20)
    listener.set_orchestrator_prices(
        {
            "BTC/USD": {
                DataTypes.SPOT: {
                    s: SpotEntry("BTC/USD", 1776, 1_010, s, STAKER)
                    for s in ("BINANCE", "OKX", "BYBIT")
                }
            }
        }
    )

    await listener._fetch_all_oracle_prices()

    assert not await listener._does_oracle_needs_update()


@pytest.mark.asyncio
async def test_read_right_after_a_flush_reuses_the_last_polled_sources():
    client = _client({"BINANCE": _own("BINANCE", 100, 1_000)})
    handler = PublisherRequestHandler(client, STAKER)
    await handler.fetch_latest_entries(BTC_USD_PAIR, DataTypes.SPOT, ["BINANCE"])

    (entry,) = await handler.fetch_latest_entries(BTC_USD_PAIR, DataTypes.SPOT, [])

    assert entry.price == 100
