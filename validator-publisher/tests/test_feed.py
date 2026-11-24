from types import SimpleNamespace
from unittest.mock import AsyncMock

from pragma_sdk.common.utils import str_to_felt

from validator_publisher.chain import OracleSpotEntry, decode_spot_entries
from validator_publisher.deployments import PAIR_SOURCES, pair_sources
from validator_publisher.feed import (
    FeedStatus,
    WithheldReason,
    read_feed,
    read_pilot_feed,
)

NOW = 1_800_000_000
BTC = str_to_felt("BTC/USD")
HONEST = (1, 2, 3)
ATTACKER = 9

MARKETS = ["BINANCE", "OKX", "BYBIT", "KUCOIN", "GATEIO"]
# the registry allow-list of the Sepolia pilot, shared by every pair
REGISTRY_SOURCES = [
    "BINANCE",
    "BITGET",
    "BITSTAMP",
    "BYBIT",
    "GATEIO",
    "HUOBI",
    "KUCOIN",
    "LBANK",
    "OKX",
    "UPBIT",
    "EKUBO",
]


def _entry(source: str, publisher: int, price: int, age: int = 60):
    return OracleSpotEntry(NOW - age, str_to_felt(source), publisher, price)


def _all(sources, publishers=HONEST, price=100, age=60):
    return [_entry(s, p, price, age) for s in sources for p in publishers]


def _read(entries, decimals=0, active=HONEST, allowed=MARKETS, **kwargs):
    return read_feed(
        "BTC/USD",
        entries,
        NOW,
        decimals=decimals,
        active_publishers=set(active),
        allowed_sources={str_to_felt(s) for s in allowed},
        **kwargs,
    )


def _read_pair(pair, entries, active):
    # what read_pilot_feed hands to read_feed
    return read_feed(
        pair,
        entries,
        NOW,
        decimals=0,
        active_publishers=set(active),
        allowed_sources={str_to_felt(s) for s in REGISTRY_SOURCES} & pair_sources(pair),
    )


def test_quorum_counts_markets_not_publishers():
    reading = _read(_all(["BINANCE", "OKX", "BYBIT"]))
    assert reading.status == FeedStatus.WITHHELD
    assert reading.withheld_reason == WithheldReason.MARKETS
    assert reading.price is None
    assert (reading.markets, reading.publishers) == (3, 3)


def test_exactly_four_markets_and_three_operators_is_valid():
    reading = _read(_all(MARKETS[:4]))
    assert reading.status == FeedStatus.VALID
    assert (reading.markets, reading.publishers) == (4, 3)


def test_stale_entries_do_not_count_toward_the_quorum():
    entries = _all(MARKETS[:3]) + _all(["KUCOIN"], age=3000)
    reading = _read(entries)
    assert reading.status == FeedStatus.WITHHELD
    assert reading.markets == 3


def test_valid_feed_takes_the_median_per_market_then_across_markets():
    entries = [
        _entry("BINANCE", 1, 100),
        _entry("BINANCE", 2, 104),
        _entry("BINANCE", 3, 103),
        _entry("OKX", 1, 101),
        _entry("OKX", 2, 101),
        _entry("BYBIT", 1, 102),
        _entry("BYBIT", 3, 102),
        _entry("KUCOIN", 2, 900),
        _entry("KUCOIN", 3, 900),
    ]
    reading = _read(entries, decimals=2)
    assert reading.status == FeedStatus.VALID
    assert reading.price == 1.025
    assert (reading.markets, reading.publishers) == (4, 3)


def test_no_fresh_entry_is_stale():
    reading = _read(_all(MARKETS[:4], age=5000))
    assert reading.status == FeedStatus.STALE
    assert reading.withheld_reason is None
    assert reading.newest_age_s == 5000


def test_no_entry_at_all_is_stale():
    reading = _read([])
    assert reading.status == FeedStatus.STALE
    assert reading.newest_age_s is None


def test_revoked_operator_entries_stop_counting_at_once():
    entries = _all(MARKETS[:4]) + [_entry("OKX", 4, 500)]
    reading = _read(entries, active=[1, 2, 3])
    assert reading.status == FeedStatus.VALID
    assert reading.price == 100
    reading = _read(entries, active=[3, 4])
    assert reading.status == FeedStatus.WITHHELD
    assert reading.withheld_reason == WithheldReason.OPERATORS
    assert (reading.publishers, reading.excluded) == (2, 8)


def test_sources_removed_from_the_registry_stop_counting_at_once():
    reading = _read(_all(MARKETS[:4]), allowed=MARKETS[:3])
    assert reading.status == FeedStatus.WITHHELD
    assert (reading.markets, reading.excluded) == (3, 3)


def test_one_operator_cannot_reach_the_quorum_with_its_own_labels():
    # audit H-1: one operator publishing under four source names
    reading = _read(_all(MARKETS[:4], publishers=[ATTACKER]), active=[ATTACKER])
    assert reading.status == FeedStatus.WITHHELD
    assert reading.withheld_reason == WithheldReason.OPERATORS
    assert reading.publishers == 1


def test_two_operators_are_below_the_operator_quorum():
    reading = _read(_all(MARKETS, publishers=[1, 2]), active=[1, 2])
    assert reading.status == FeedStatus.WITHHELD
    assert reading.withheld_reason == WithheldReason.OPERATORS


def test_operator_quorum_can_be_lowered_to_test_with_one_operator():
    reading = _read(_all(MARKETS[:4], publishers=[1]), active=[1], min_operators=1)
    assert reading.status == FeedStatus.VALID


def test_labels_off_the_pair_are_not_markets():
    # audit H-1: USDT/USD is quoted on 6 of the 11 allowed sources. The
    # attacker fills the 5 free labels while Ekubo is down for everyone.
    honest = _all(["BINANCE", "BITGET", "BITSTAMP", "BYBIT", "UPBIT"])
    free = set(REGISTRY_SOURCES) - PAIR_SOURCES["USDT/USD"]
    assert len(free) == 5
    attack = _all(free, publishers=[ATTACKER], price=110)
    reading = _read_pair("USDT/USD", honest + attack, active=HONEST + (ATTACKER,))
    assert reading.status == FeedStatus.VALID
    assert reading.price == 100
    assert (reading.markets, reading.excluded) == (5, 5)


def test_market_published_by_a_minority_of_operators_is_not_counted():
    # the honest fetchers of 4 real BTC markets fail, the attacker fills them
    honest = _all(["BINANCE", "BYBIT", "OKX", "KUCOIN"])
    attack = _all(
        ["BITSTAMP", "GATEIO", "HUOBI", "LBANK"], publishers=[ATTACKER], price=1000
    )
    reading = _read_pair("BTC/USD", honest + attack, active=HONEST + (ATTACKER,))
    assert reading.status == FeedStatus.VALID
    assert reading.price == 100
    assert (reading.markets, reading.minority_markets) == (4, 4)


def test_half_of_the_operators_is_not_a_majority():
    entries = _all(MARKETS[:4], publishers=[1, 2, 3, 4]) + _all(
        ["GATEIO"], publishers=[1, 2], price=1000
    )
    reading = _read(entries, active=[1, 2, 3, 4])
    assert reading.status == FeedStatus.VALID
    assert reading.price == 100
    assert (reading.markets, reading.minority_markets) == (4, 1)


def test_minority_operator_on_every_market_does_not_move_the_price():
    honest = _all(PAIR_SOURCES["BTC/USD"])
    attack = _all(PAIR_SOURCES["BTC/USD"], publishers=[ATTACKER], price=1000)
    reading = _read_pair("BTC/USD", honest + attack, active=HONEST + (ATTACKER,))
    assert reading.status == FeedStatus.VALID
    assert reading.price == 100
    assert reading.publishers == 4


def test_an_operator_counts_once_per_market():
    entries = _all(MARKETS[:4]) + [_entry("BINANCE", 1, 900, age=10)] * 3
    reading = _read(entries)
    assert reading.status == FeedStatus.VALID
    assert reading.price == 100


def test_every_pilot_pair_has_enough_sources_on_the_registry():
    registry = {str_to_felt(s) for s in REGISTRY_SOURCES}
    for pair in PAIR_SOURCES:
        assert len(pair_sources(pair) & registry) >= 4, pair


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
            return_value=_all(["BINANCE", "OKX", "BYBIT", "KUCOIN"], price=10**8)
            + _all(["UPBIT"], price=10**9)
        ),
        block_timestamp=AsyncMock(return_value=NOW),
        decimals=AsyncMock(return_value=8),
        publisher_status=AsyncMock(return_value="ACTIVE"),
        allowed_sources=AsyncMock(
            return_value=[str_to_felt(s) for s in REGISTRY_SOURCES]
        ),
    )
    reading = await read_pilot_feed(chain, "BTC/USD")
    assert reading.status == FeedStatus.VALID
    assert reading.price == 1.0
    # UPBIT is allowed by the registry but quotes no BTC/USD market
    assert (reading.markets, reading.excluded) == (4, 3)
    chain.spot_entries.assert_awaited_once_with("BTC/USD")
    assert chain.publisher_status.await_count == 3


async def test_read_pilot_feed_operator_quorum_can_be_lowered():
    chain = SimpleNamespace(
        spot_entries=AsyncMock(
            return_value=_all(MARKETS[:4], publishers=[1], price=10**8)
        ),
        block_timestamp=AsyncMock(return_value=NOW),
        decimals=AsyncMock(return_value=8),
        publisher_status=AsyncMock(return_value="ACTIVE"),
        allowed_sources=AsyncMock(return_value=[str_to_felt(s) for s in MARKETS]),
    )
    assert (await read_pilot_feed(chain, "BTC/USD")).status == FeedStatus.WITHHELD
    reading = await read_pilot_feed(chain, "BTC/USD", min_operators=1)
    assert reading.status == FeedStatus.VALID
