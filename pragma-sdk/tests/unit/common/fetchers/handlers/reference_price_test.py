import aiohttp
import pytest

from aioresponses import aioresponses

from pragma_sdk.common.fetchers.handlers.reference_price import (
    ReferencePriceError,
    ReferencePriceProvider,
)

COINBASE = "https://api.coinbase.com/v2/prices/ETH-USD/spot"
KRAKEN = "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"
BINANCE = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"


def _kraken_payload(last: str):
    return {"error": [], "result": {"XETHZUSD": {"c": [last, "1.0"]}}}


@pytest.mark.asyncio
async def test_median_of_independent_sources():
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BINANCE, payload={"price": "2448.32"})
        async with aiohttp.ClientSession() as session:
            price = await provider.get_price("ETH", "USD", session)
    assert price == 2447.34


@pytest.mark.asyncio
async def test_quorum_not_met_fails_closed():
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, status=503)
        m.get(BINANCE, status=429)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ReferencePriceError, match="quorum"):
                await provider.get_price("ETH", "USD", session)


@pytest.mark.asyncio
async def test_disagreeing_sources_fail_closed():
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BINANCE, payload={"price": "4990.00"})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ReferencePriceError, match="disagree"):
                await provider.get_price("ETH", "USD", session)


@pytest.mark.asyncio
async def test_stables_are_one_without_any_request():
    provider = ReferencePriceProvider()
    with aioresponses():
        # no mocked endpoint: any HTTP call would raise
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USDT", "USD", session) == 1.0
            assert await provider.get_price("USDC", "USD", session) == 1.0
            assert await provider.get_price("USDC", "USDPLUS", session) == 1.0


@pytest.mark.asyncio
async def test_cross_quote_uses_both_usd_references():
    provider = ReferencePriceProvider(cache_ttl_seconds=0)
    with aioresponses() as m:
        for url, payload in [
            (COINBASE, {"data": {"amount": "2000"}}),
            (KRAKEN, _kraken_payload("2000")),
            (BINANCE, {"price": "2000"}),
            (
                "https://api.coinbase.com/v2/prices/BTC-USD/spot",
                {"data": {"amount": "80000"}},
            ),
            (
                "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
                {"error": [], "result": {"XXBTZUSD": {"c": ["80000", "1"]}}},
            ),
            (
                "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                {"price": "80000"},
            ),
        ]:
            m.get(url, payload=payload)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "BTC", session) == 0.025


@pytest.mark.asyncio
async def test_cache_shares_one_lookup():
    provider = ReferencePriceProvider(cache_ttl_seconds=60)
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BINANCE, payload={"price": "2448.32"})
        async with aiohttp.ClientSession() as session:
            first = await provider.get_price("ETH", "USD", session)
            # endpoints are single-shot in aioresponses: a second HTTP round
            # would fail the quorum
            second = await provider.get_price("ETH", "USD", session)
    assert first == second == 2447.34


@pytest.mark.asyncio
async def test_concurrent_lookups_share_one_http_round():
    # 20+ fetchers ask for ETH/USD at the same instant on a cold cache; the
    # per-ticker lock must serialise them onto a single HTTP round.
    import asyncio

    provider = ReferencePriceProvider(cache_ttl_seconds=60)
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BINANCE, payload={"price": "2448.32"})
        async with aiohttp.ClientSession() as session:
            prices = await asyncio.gather(
                *(provider.get_price("ETH", "USD", session) for _ in range(20))
            )
    assert prices == [2447.34] * 20
