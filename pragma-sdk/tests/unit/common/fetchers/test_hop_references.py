"""
Hopped pairs must be rebased with off-chain references only, and fail closed
when no reference is available. Covers HopHandler, the EVM oracle feeds
(WSTETH/USD = WSTETH/ETH x ETH/USD), Pyth's hopped feeds and the CEX
rebasing operator.
"""

import pytest

from unittest import mock

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    FeedConfig,
)
from pragma_sdk.common.fetchers.fetchers.binance import BinanceFetcher
from pragma_sdk.common.fetchers.fetchers.okx import OkxFetcher
from pragma_sdk.common.fetchers.fetchers.pyth import PythFetcher, PYTH_HOPPED_FEEDS
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.fetchers.handlers.reference_price import ReferencePriceError
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair

from tests.unit.common.fetchers.test_evm_oracle import FakeSession


class StubProvider:
    def __init__(self, prices=None, error=None):
        self.prices = prices or {}
        self.error = error
        self.calls = []

    async def get_price(self, base, quote="USD", session=None):
        self.calls.append((base, quote))
        if self.error:
            raise self.error
        return self.prices[(base, quote)]


# ---------------------------------------------------------------- HopHandler


@pytest.mark.asyncio
async def test_hop_prices_come_from_the_reference_provider():
    handler = HopHandler(hopped_currencies={"USD": "ETH"})
    provider = StubProvider({("ETH", "USD"): 2500.0})

    prices = await handler.get_hop_prices(session=None, provider=provider)

    assert prices == {Pair.from_tickers("ETH", "USD"): 2500.0}
    assert provider.calls == [("ETH", "USD")]


@pytest.mark.asyncio
async def test_hop_prices_propagate_reference_failure():
    handler = HopHandler(hopped_currencies={"USD": "ETH"})
    provider = StubProvider(error=ReferencePriceError("quorum"))

    with pytest.raises(ReferencePriceError):
        await handler.get_hop_prices(session=None, provider=provider)


def test_hop_handler_has_no_onchain_client_parameter():
    # Passing the Pragma client is the feedback loop we removed: it must not
    # be accepted anymore, even by name.
    import inspect

    params = inspect.signature(HopHandler.get_hop_prices).parameters
    assert "client" not in params


# ---------------------------------------------------------- EVM oracle feeds


class WstETHLikeFetcher(EVMOracleFeedFetcher):
    SOURCE = "TEST_WSTETH"
    hop_handler = HopHandler(hopped_currencies={"USD": "ETH"})

    def __init__(self):
        self._rpc_urls = ["https://rpc-1"]
        self._rpc_index = 0
        self._rpc_failures = {}
        self._request_id = 0
        self.publisher = "TEST"
        self.pairs = [Pair.from_tickers("WSTETH", "USD")]
        self.feed_configs = {
            "WSTETH/ETH": FeedConfig(contract_address="0x1", decimals=0)
        }


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_evm_feed_rebases_with_offchain_reference():
    fetcher = WstETHLikeFetcher()
    # feed answers WSTETH/ETH = 1.2 (decimals=0 -> raw 0x1 would be 1, use 0x6/5)
    fetcher.feed_configs["WSTETH/ETH"] = FeedConfig(contract_address="0x1", decimals=1)
    session = FakeSession(
        {"https://rpc-1": [{"status": 200, "payload": {"result": "0xc"}}]}
    )
    provider = StubProvider({("ETH", "USD"): 2500.0})

    with mock.patch(
        "pragma_sdk.common.fetchers.handlers.hop_handler.get_reference_price_provider",
        return_value=provider,
    ):
        result = await fetcher.fetch(session)

    assert result == [
        SpotEntry(
            "WSTETH/USD",
            int(1.2 * 2500.0 * 10**8),
            12345,
            "TEST_WSTETH",
            "TEST",
            volume=0,
        )
    ]
    assert provider.calls == [("ETH", "USD")]


@pytest.mark.asyncio
async def test_evm_feed_fails_closed_without_reference():
    fetcher = WstETHLikeFetcher()
    session = FakeSession(
        {"https://rpc-1": [{"status": 200, "payload": {"result": "0x1"}}]}
    )
    provider = StubProvider(error=ReferencePriceError("quorum not met"))

    with mock.patch(
        "pragma_sdk.common.fetchers.handlers.hop_handler.get_reference_price_provider",
        return_value=provider,
    ):
        result = await fetcher.fetch(session)

    assert len(result) == 1
    assert isinstance(result[0], PublisherFetchError)
    assert "Missing hop prices" in str(result[0])


# ------------------------------------------------------------------- Pyth


@pytest.mark.asyncio
async def test_pyth_hopped_feed_uses_offchain_reference():
    pair = Pair.from_tickers("WSTETH", "USD")
    fetcher = PythFetcher([pair], "TEST")
    hopped = PYTH_HOPPED_FEEDS["WSTETH/USD"]
    feed = {"price": {"price": "120000000", "expo": -8, "publish_time": 12345}}
    provider = StubProvider({("ETH", "USD"): 2500.0})

    with (
        mock.patch(
            "pragma_sdk.common.fetchers.fetchers.pyth.get_reference_price_provider",
            return_value=provider,
        ),
        mock.patch.object(fetcher.client, "get_spot") as get_spot,
    ):
        entry = await fetcher._construct_hopped(pair, feed, hopped, session=None)

    assert entry == SpotEntry(
        "WSTETH/USD", int(1.2 * 2500.0 * 10**8), 12345, "PYTH", "TEST"
    )
    assert get_spot.call_count == 0


@pytest.mark.asyncio
async def test_pyth_hopped_feed_fails_closed_without_reference():
    pair = Pair.from_tickers("WSTETH", "USD")
    fetcher = PythFetcher([pair], "TEST")
    hopped = PYTH_HOPPED_FEEDS["WSTETH/USD"]
    feed = {"price": {"price": "120000000", "expo": -8, "publish_time": 12345}}

    with mock.patch(
        "pragma_sdk.common.fetchers.fetchers.pyth.get_reference_price_provider",
        return_value=StubProvider(error=ReferencePriceError("quorum")),
    ):
        entry = await fetcher._construct_hopped(pair, feed, hopped, session=None)

    assert isinstance(entry, PublisherFetchError)


# ----------------------------------------------------- CEX rebasing operator


@mock.patch("time.time", mock.MagicMock(return_value=12345))
def test_cex_rebasing_multiplies_by_usdt_usd():
    # raw quote is USDT per BTC, usdt_price is USD per USDT: BTC/USD is the
    # product. Dividing (the 2026-09-04 bug) would print -51% for a 2.04 hop.
    pair = Pair.from_tickers("BTC", "USD")
    binance = BinanceFetcher([pair], "TEST")
    okx = OkxFetcher([pair], "TEST")

    b = binance._construct(
        pair, {"bidPrice": "80000", "askPrice": "80000"}, usdt_price=0.98
    )
    o = okx._construct(
        pair, {"data": [{"last": "80000", "volCcy24h": "0"}]}, usdt_price=0.98
    )

    assert b.price == int(80000 * 0.98 * 10**8)
    assert o.price == int(80000 * 0.98 * 10**8)
