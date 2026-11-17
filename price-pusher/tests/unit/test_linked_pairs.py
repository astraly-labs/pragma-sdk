"""
ETH/USD, STETH/USD and WSTETH/USD are separate on-chain medians: pushing one
without the others moves the implied stETH/ETH and wstETH/ETH rates.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.types import DataTypes

from price_pusher.configs import PriceConfig
from price_pusher.core.listener import PriceListener
from price_pusher.core.poller import PricePoller
from price_pusher.core import pusher as pusher_module
from price_pusher.core.pusher import PricePusher
from price_pusher.linked_pairs import linked_first, with_linked_pairs
from price_pusher.orchestrator import Orchestrator

ETH, STETH, WSTETH, BTC = (
    Pair.from_tickers(*p.split("/"))
    for p in ("ETH/USD", "STETH/USD", "WSTETH/USD", "BTC/USD")
)


def _entry(pair: str, source: str) -> SpotEntry:
    return SpotEntry(pair, 100, 1_000, source, "PRAGMA")


def _listener(pairs, deviation):
    config = PriceConfig(
        pairs={"spot": [str(p) for p in pairs]},
        time_difference=1800,
        price_deviation=deviation,
    )
    return PriceListener(MagicMock(), config, polling_frequency_in_s=20)


def test_linked_pairs_are_added_when_configured():
    known = {str(p): p for p in (ETH, STETH, WSTETH, BTC)}

    expanded = with_linked_pairs({DataTypes.SPOT: [BTC, ETH]}, known)

    assert [str(p) for p in expanded[DataTypes.SPOT]] == [
        "BTC/USD",
        "ETH/USD",
        "STETH/USD",
        "WSTETH/USD",
    ]


def test_unconfigured_linked_pairs_are_skipped():
    known = {str(p): p for p in (ETH, BTC)}

    expanded = with_linked_pairs({DataTypes.SPOT: [ETH]}, known)

    assert [str(p) for p in expanded[DataTypes.SPOT]] == ["ETH/USD"]


def test_unlinked_groups_are_unchanged():
    known = {str(p): p for p in (ETH, STETH, WSTETH, BTC)}
    pairs = {DataTypes.SPOT: [BTC]}

    assert with_linked_pairs(pairs, known) == pairs


def test_linked_entries_come_first_and_contiguous():
    entries = [
        _entry("BTC/USD", "BINANCE"),
        _entry("ETH/USD", "BINANCE"),
        _entry("USDC/USD", "OKX"),
        _entry("WSTETH/USD", "LIDO"),
        _entry("ETH/USD", "OKX"),
    ]

    ordered = [(e.get_pair_id(), e.get_source()) for e in linked_first(entries)]

    assert ordered == [
        ("ETH/USD", "BINANCE"),
        ("WSTETH/USD", "LIDO"),
        ("ETH/USD", "OKX"),
        ("BTC/USD", "BINANCE"),
        ("USDC/USD", "OKX"),
    ]


@pytest.mark.parametrize("trigger", ["eth", "lst"])
def test_flushing_one_group_flushes_the_linked_pairs(trigger):
    eth_group = _listener([BTC, ETH], 0.01)
    lst_group = _listener([STETH, WSTETH], 0.025)
    orchestrator = Orchestrator(
        poller=AsyncMock(spec=PricePoller),
        listeners=[eth_group, lst_group],
        pusher=AsyncMock(spec=PricePusher),
    )
    orchestrator.callback_update_prices(
        [
            _entry("BTC/USD", "BINANCE"),
            _entry("ETH/USD", "BINANCE"),
            _entry("STETH/USD", "OKX"),
            _entry("WSTETH/USD", "LIDO"),
        ]
    )
    listener = eth_group if trigger == "eth" else lst_group

    flushed = orchestrator._flush_entries_for_assets(
        with_linked_pairs(listener.data_config, orchestrator.known_spot_pairs)
    )

    pairs = {e.get_pair_id() for e in flushed}
    assert {"ETH/USD", "STETH/USD", "WSTETH/USD"} <= pairs
    assert ("BTC/USD" in pairs) == (trigger == "eth")


@pytest.mark.asyncio
async def test_pusher_publishes_linked_entries_first(monkeypatch):
    monkeypatch.setattr(pusher_module.asyncio, "sleep", AsyncMock())
    client = SimpleNamespace(
        publish_many=AsyncMock(return_value=[]),
        execution_config=SimpleNamespace(pagination=40),
    )
    pusher = PricePusher(client=client)
    pusher.wait_for_publishing_acceptance = AsyncMock()

    await pusher.update_price_feeds(
        [_entry("BTC/USD", "BINANCE"), _entry("WSTETH/USD", "LIDO")]
    )

    (published,) = client.publish_many.call_args.args
    assert [e.get_pair_id() for e in published] == ["WSTETH/USD", "BTC/USD"]


@pytest.mark.asyncio
async def test_group_flushed_by_a_linked_push_does_not_count_as_empty_oracle():
    lst_group = _listener([STETH, WSTETH], 0.025)
    # ETH/USD polled, STETH/WSTETH just flushed by the ETH group's push
    lst_group.set_orchestrator_prices({"ETH/USD": {DataTypes.SPOT: {}}})

    for _ in range(20):
        assert not await lst_group._does_oracle_needs_update()
    assert lst_group.consecutive_empty_oracle_error == 0
