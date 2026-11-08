import asyncio

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.utils import str_to_felt

import pytest

from validator_publisher import source_coverage
from validator_publisher.source_coverage import (
    CoverageOrchestrator,
    count_allowed_sources,
)

PUBLISHER = "0x77d4"
ALLOWED = {str_to_felt(s) for s in ["BINANCE", "OKX", "BYBIT", "KUCOIN", "GATEIO"]}


def _entries(pair: str, *sources: str):
    return [SpotEntry(pair, 100, 1, source, PUBLISHER) for source in sources]


def _orchestrator(**kwargs) -> CoverageOrchestrator:
    defaults = dict(
        pairs=["BTC/USD", "ETH/USD"],
        allowed_sources=ALLOWED,
        poller=MagicMock(),
        listeners=[],
        pusher=SimpleNamespace(miden_client=None),
    )
    defaults.update(kwargs)
    return CoverageOrchestrator(**defaults)


def test_count_ignores_disallowed_and_duplicate_sources():
    entries = _entries("BTC/USD", "BINANCE", "BINANCE", "OKX", "COINBASE")
    assert count_allowed_sources(entries, ALLOWED) == {"BTC/USD": 2}


def test_sources_that_answered_are_still_published():
    orchestrator = _orchestrator(pairs=["BTC/USD"])
    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE", "OKX"))
    assert len(orchestrator.latest_prices["BTC/USD"][DataTypes.SPOT]) == 2
    assert orchestrator.degraded == {"BTC/USD"}


def test_degraded_pair_recovers():
    orchestrator = _orchestrator(pairs=["BTC/USD"])
    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE"))
    orchestrator.callback_update_prices(
        _entries("BTC/USD", "BINANCE", "OKX", "BYBIT", "KUCOIN")
    )
    assert orchestrator.degraded == set()


def test_coverage_is_reported_for_every_configured_pair():
    seen = {}
    orchestrator = _orchestrator(on_coverage=lambda pair, n: seen.__setitem__(pair, n))
    orchestrator.callback_update_prices(_entries("BTC/USD", "BINANCE", "OKX"))
    assert seen == {"BTC/USD": 2, "ETH/USD": 0}


@pytest.mark.asyncio
async def test_allowed_sources_refresh_keeps_the_last_set_on_error(monkeypatch):
    monkeypatch.setattr(source_coverage, "ALLOWED_SOURCES_REFRESH_S", 0)
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
