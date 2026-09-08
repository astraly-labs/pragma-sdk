"""
The oracle rejects a whole publish batch on the first entry whose source is not
whitelisted for the publisher. The pusher must drop those entries itself.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pragma_sdk.common.fetchers import metrics as metrics_module
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.utils import str_to_felt

from price_pusher.core import pusher as pusher_module
from price_pusher.core.pusher import PricePusher


class RecordingSink:
    def __init__(self):
        self.rejected_events = []

    def entry(self, pair, source):
        pass

    def rejected(self, pair, source, reason):
        self.rejected_events.append((pair, source, reason))

    def deviation(self, pair, source, deviation):
        pass

    def reference_failure(self, ticker, reason):
        pass

    def reference_venue_failure(self, ticker, venue):
        pass

    def stable_price(self, ticker, price):
        pass


def _entry(source: str) -> SpotEntry:
    return SpotEntry("BTC/USD", 80_000 * 10**8, 12345, source, "PRAGMA")


def _client(allowed: list[str] | Exception):
    client = SimpleNamespace()
    client.publish_many = AsyncMock(return_value=[])
    if isinstance(allowed, Exception):
        client.get_publisher_sources = AsyncMock(side_effect=allowed)
    else:
        client.get_publisher_sources = AsyncMock(
            return_value=[str_to_felt(s) for s in allowed]
        )
    return client


@pytest.fixture
def sink(monkeypatch):
    sink = RecordingSink()
    monkeypatch.setattr(metrics_module, "_sink", sink)
    monkeypatch.setattr(pusher_module.asyncio, "sleep", AsyncMock())
    return sink


@pytest.mark.asyncio
async def test_non_whitelisted_source_is_dropped_before_publishing(sink):
    client = _client(["BINANCE", "BITSTAMP"])
    pusher = PricePusher(client, publisher_name="PRAGMA")
    pusher.wait_for_publishing_acceptance = AsyncMock()

    binance, kraken = _entry("BINANCE"), _entry("KRAKEN")
    await pusher.update_price_feeds([binance, kraken])

    client.publish_many.assert_awaited_once_with([binance])
    assert sink.rejected_events == [("BTC/USD", "KRAKEN", "source_not_whitelisted")]
    assert pusher.consecutive_push_error == 0


@pytest.mark.asyncio
async def test_nothing_left_means_no_push_and_no_error(sink):
    client = _client(["BINANCE"])
    pusher = PricePusher(client, publisher_name="PRAGMA")

    assert await pusher.update_price_feeds([_entry("KRAKEN")]) is None
    client.publish_many.assert_not_awaited()
    assert pusher.consecutive_push_error == 0


@pytest.mark.asyncio
async def test_unreadable_registry_does_not_filter(sink):
    client = _client(RuntimeError("rpc down"))
    pusher = PricePusher(client, publisher_name="PRAGMA")
    pusher.wait_for_publishing_acceptance = AsyncMock()

    entries = [_entry("BINANCE"), _entry("KRAKEN")]
    await pusher.update_price_feeds(entries)

    client.publish_many.assert_awaited_once_with(entries)
    assert sink.rejected_events == []


@pytest.mark.asyncio
async def test_whitelist_is_cached_and_read_failures_keep_it(sink):
    client = _client(["BINANCE"])
    pusher = PricePusher(client, publisher_name="PRAGMA")
    pusher.wait_for_publishing_acceptance = AsyncMock()

    await pusher.update_price_feeds([_entry("BINANCE")])
    await pusher.update_price_feeds([_entry("BINANCE")])
    assert client.get_publisher_sources.await_count == 1  # within the TTL

    pusher._allowed_sources_at = 0.0  # expire the cache
    client.get_publisher_sources = AsyncMock(side_effect=RuntimeError("rpc down"))
    await pusher.update_price_feeds([_entry("BINANCE"), _entry("KRAKEN")])
    # previous whitelist still applied
    assert client.publish_many.await_args.args[0] == [_entry("BINANCE")]


@pytest.mark.asyncio
async def test_client_without_registry_access_is_untouched(sink):
    client = SimpleNamespace(publish_many=AsyncMock(return_value=[]))
    pusher = PricePusher(client, publisher_name="PRAGMA")
    pusher.wait_for_publishing_acceptance = AsyncMock()

    entries = [_entry("KRAKEN")]
    await pusher.update_price_feeds(entries)
    client.publish_many.assert_awaited_once_with(entries)
