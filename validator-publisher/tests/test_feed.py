from types import SimpleNamespace
from unittest.mock import AsyncMock

from pragma_sdk.common.utils import str_to_felt

from validator_publisher.chain import OracleSpotEntry, decode_spot_entries
from validator_publisher.feed import FeedStatus, read_feed, read_pilot_feed

NOW = 1_800_000_000
BTC = str_to_felt("BTC/USD")


MARKETS = ["BINANCE", "OKX", "BYBIT", "KUCOIN", "GATEIO"]


def _entry(source: str, publisher: int, price: int, age: int = 60):
    return OracleSpotEntry(NOW - age, str_to_felt(source), publisher, price)


def _read(entries, decimals=0, active=(1, 2, 3), allowed=MARKETS):
    return read_feed(
        "BTC/USD",
        entries,
        NOW,
        decimals=decimals,
        active_publishers=set(active),
        allowed_sources={str_to_felt(s) for s in allowed},
    )


def test_quorum_counts_markets_not_publishers():
    entries = [
        _entry(s, p, 100) for s in ["BINANCE", "OKX", "BYBIT"] for p in (1, 2, 3)
    ]
    reading = _read(entries)
    assert reading.status == FeedStatus.WITHHELD
    assert reading.price is None
    assert (reading.markets, reading.publishers) == (3, 3)


def test_stale_entries_do_not_count_toward_the_quorum():
    entries = [
        _entry("BINANCE", 1, 100),
        _entry("OKX", 1, 100),
        _entry("BYBIT", 1, 100),
        _entry("KUCOIN", 2, 100, age=3000),
    ]
    reading = _read(entries)
    assert reading.status == FeedStatus.WITHHELD
    assert reading.markets == 3


def test_valid_feed_takes_the_median_per_market_then_across_markets():
    entries = [
        _entry("BINANCE", 1, 100),
        _entry("BINANCE", 2, 104),
        _entry("OKX", 1, 101),
        _entry("BYBIT", 1, 102),
        _entry("KUCOIN", 2, 900),
    ]
    reading = _read(entries, decimals=2)
    assert reading.status == FeedStatus.VALID
    assert reading.price == 1.02
    assert (reading.markets, reading.publishers) == (4, 2)


def test_no_fresh_entry_is_stale():
    entries = [
        _entry(s, 1, 100, age=5000) for s in ["BINANCE", "OKX", "BYBIT", "KUCOIN"]
    ]
    reading = _read(entries)
    assert reading.status == FeedStatus.STALE
    assert reading.newest_age_s == 5000


def test_no_entry_at_all_is_stale():
    reading = _read([])
    assert reading.status == FeedStatus.STALE
    assert reading.newest_age_s is None


def test_revoked_operator_entries_stop_counting_at_once():
    entries = [_entry(s, 1, 100) for s in MARKETS[:4]] + [_entry("OKX", 2, 500)]
    reading = _read(entries, active=[2])
    assert reading.status == FeedStatus.WITHHELD
    assert (reading.markets, reading.publishers, reading.excluded) == (1, 1, 4)


def test_sources_removed_from_the_registry_stop_counting_at_once():
    entries = [_entry(s, 1, 100) for s in MARKETS[:4]]
    reading = _read(entries, allowed=MARKETS[:3])
    assert reading.status == FeedStatus.WITHHELD
    assert (reading.markets, reading.excluded) == (3, 1)


def test_decode_spot_entries():
    raw = [2]
    raw += [0, NOW, str_to_felt("OKX"), 0xA, 101, BTC, 0]
    raw += [0, NOW - 5, str_to_felt("BYBIT"), 0xB, 102, BTC, 7]
    assert decode_spot_entries(raw) == [
        OracleSpotEntry(NOW, str_to_felt("OKX"), 0xA, 101),
        OracleSpotEntry(NOW - 5, str_to_felt("BYBIT"), 0xB, 102),
    ]


async def test_read_pilot_feed_reads_entries_clock_and_decimals():
    chain = SimpleNamespace(
        spot_entries=AsyncMock(
            return_value=[
                _entry(s, 1, 10**8) for s in ["BINANCE", "OKX", "BYBIT", "KUCOIN"]
            ]
        ),
        block_timestamp=AsyncMock(return_value=NOW),
        decimals=AsyncMock(return_value=8),
        publisher_status=AsyncMock(return_value="ACTIVE"),
        allowed_sources=AsyncMock(return_value=[str_to_felt(s) for s in MARKETS]),
    )
    reading = await read_pilot_feed(chain, "BTC/USD")
    assert reading.status == FeedStatus.VALID
    assert reading.price == 1.0
    chain.spot_entries.assert_awaited_once_with("BTC/USD")
    chain.publisher_status.assert_awaited_once_with(1)
