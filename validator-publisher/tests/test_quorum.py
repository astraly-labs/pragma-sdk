import asyncio

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.utils import str_to_felt

from validator_publisher import quorum
from validator_publisher.quorum import QuorumOrchestrator, count_allowed_sources

PUBLISHER = "0x77d4"
ALLOWED = {str_to_felt(s) for s in ["BINANCE", "OKX", "BYBIT", "KUCOIN", "GATEIO"]}


def _entries(pair: str, *sources: str):
    return [SpotEntry(pair, 100, 1, source, PUBLISHER) for source in sources]


def _orchestrator(**kwargs) -> QuorumOrchestrator:
    defaults = dict(
        pairs=["BTC/USD", "ETH/USD"],
        allowed_sources=ALLOWED,
        poller=MagicMock(),
        listeners=[],
        pusher=SimpleNamespace(miden_client=None),
    )
    defaults.update(kwargs)
    return QuorumOrchestrator(**defaults)


def test_count_ignores_disallowed_and_duplicate_sources():
    entries = _entries("BTC/USD", "BINANCE", "BINANCE", "OKX", "COINBASE")
    assert count_allowed_sources(entries, ALLOWED) == {"BTC/USD": 2}


def test_pair_below_quorum_is_withheld():
    orchestrator = _orchestrator()
    orchestrator.callback_update_prices(
        _entries("BTC/USD", "BINANCE", "OKX", "BYBIT", "COINBASE", "KRAKEN")
        + _entries("ETH/USD", "BINANCE", "OKX", "BYBIT", "KUCOIN")
    )
    assert "BTC/USD" not in orchestrator.latest_prices
    assert len(orchestrator.latest_prices["ETH/USD"][DataTypes.SPOT]) == 4
    assert orchestrator.withheld == {"BTC/USD"}


def test_prices_from_an_earlier_poll_are_not_published():
    orchestrator = _orchestrator(pairs=["BTC/USD"])
    orchestrator.callback_update_prices(
        _entries("BTC/USD", "BINANCE", "OKX", "BYBIT", "KUCOIN")
    )
    assert "BTC/USD" in orchestrator.latest_prices

    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE", "OKX"))
    assert orchestrator.latest_prices == {}
    assert orchestrator._flush_entries_for_assets({DataTypes.SPOT: []}) == []


def test_pair_is_published_again_once_quorum_is_back():
    orchestrator = _orchestrator(pairs=["BTC/USD"])
    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE"))
    assert orchestrator.withheld == {"BTC/USD"}

    orchestrator.callback_update_prices(
        _entries("BTC/USD", "BINANCE", "OKX", "BYBIT", "KUCOIN")
    )
    assert orchestrator.withheld == set()
    assert len(orchestrator.latest_prices["BTC/USD"][DataTypes.SPOT]) == 4


def test_listeners_keep_the_same_prices_dict():
    listener = MagicMock()
    orchestrator = _orchestrator(pairs=["BTC/USD"], listeners=[listener])
    shared = listener.set_orchestrator_prices.call_args.args[0]
    orchestrator.callback_update_prices(
        _entries("BTC/USD", "BINANCE", "OKX", "BYBIT", "KUCOIN")
    )
    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE"))
    assert shared is orchestrator.latest_prices
    assert shared == {}


def test_quorum_is_reported_for_every_configured_pair():
    seen = {}
    orchestrator = _orchestrator(on_quorum=lambda pair, n: seen.__setitem__(pair, n))
    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE", "OKX"))
    assert seen == {"BTC/USD": 2, "ETH/USD": 0}


@pytest.mark.asyncio
async def test_allowed_sources_refresh_keeps_the_last_set_on_error(monkeypatch):
    monkeypatch.setattr(quorum, "ALLOWED_SOURCES_REFRESH_S", 0)
    orchestrator = _orchestrator()
    chain = SimpleNamespace(
        allowed_sources=AsyncMock(
            side_effect=[
                [str_to_felt("OKX")],
                RuntimeError("rpc down"),
                asyncio.CancelledError,
            ]
        )
    )
    with pytest.raises(asyncio.CancelledError):
        await orchestrator.refresh_allowed_sources_forever(chain)
    assert orchestrator.allowed_sources == {str_to_felt("OKX")}
