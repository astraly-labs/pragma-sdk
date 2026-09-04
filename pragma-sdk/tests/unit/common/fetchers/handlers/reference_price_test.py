import asyncio

import aiohttp
import pytest

from aioresponses import aioresponses

from pragma_sdk.common.fetchers.handlers.reference_price import (
    DEFAULT_SOURCES,
    ReferencePriceError,
    ReferencePriceProvider,
)

COINBASE = "https://api.coinbase.com/v2/prices/ETH-USD/spot"
KRAKEN = "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"
BINANCE = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"
BITSTAMP = "https://www.bitstamp.net/api/v2/ticker/ethusd/"
GEMINI = "https://api.gemini.com/v1/pubticker/ethusd"
BITFINEX = "https://api-pub.bitfinex.com/v2/ticker/tETHUSD"
OKX = "https://www.okx.com/api/v5/market/ticker?instId=ETH-USDT"
BYBIT = "https://api.bybit.com/v5/market/tickers?category=spot&symbol=ETHUSDT"
KUCOIN = "https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=ETH-USDT"


def _kraken_payload(last: str):
    return {"error": [], "result": {"XETHZUSD": {"c": [last, "1.0"]}}}


def _mock_all_nine(m, eth: float, bitfinex: float | None = None):
    """Mock every default venue at `eth`, bitfinex optionally elsewhere."""
    m.get(COINBASE, payload={"data": {"amount": str(eth)}})
    m.get(KRAKEN, payload=_kraken_payload(str(eth)))
    m.get(BITSTAMP, payload={"bid": str(eth), "ask": str(eth), "volume": "100"})
    m.get(GEMINI, payload={"bid": str(eth), "ask": str(eth)})
    bf = eth if bitfinex is None else bitfinex
    m.get(BITFINEX, payload=[bf, 1.0, bf, 1.0])
    m.get(BINANCE, payload={"price": str(eth)})
    m.get(OKX, payload={"data": [{"last": str(eth)}]})
    m.get(BYBIT, payload={"result": {"list": [{"lastPrice": str(eth)}]}})
    m.get(KUCOIN, payload={"data": {"price": str(eth)}})


def three_venues(**kwargs) -> ReferencePriceProvider:
    """Coinbase, Kraken, Binance only, quorum 2: the compact fixture."""
    subset = tuple(
        s for s in DEFAULT_SOURCES if s[0] in ("coinbase", "kraken", "binance")
    )
    return ReferencePriceProvider(sources=subset, quorum=2, **kwargs)


def test_default_provider_has_nine_independent_venues():
    names = [name for name, _ in DEFAULT_SOURCES]
    assert len(names) == 9 and len(set(names)) == 9
    assert ReferencePriceProvider().quorum == 4


@pytest.mark.asyncio
async def test_median_of_independent_sources():
    provider = three_venues()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BINANCE, payload={"price": "2448.32"})
        async with aiohttp.ClientSession() as session:
            price = await provider.get_price("ETH", "USD", session)
    assert price == 2447.34


@pytest.mark.asyncio
async def test_all_nine_venues_answer():
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        _mock_all_nine(m, 2445.0)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "USD", session) == 2445.0


@pytest.mark.asyncio
async def test_outlier_venue_is_dropped_not_fatal():
    # Bitfinex 10% above everyone else: dropped, the other eight carry on.
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        _mock_all_nine(m, 2445.0, bitfinex=2690.0)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "USD", session) == 2445.0


@pytest.mark.asyncio
async def test_quorum_not_met_fails_closed():
    provider = three_venues()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, status=503)
        m.get(BINANCE, status=429)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ReferencePriceError, match="quorum"):
                await provider.get_price("ETH", "USD", session)


@pytest.mark.asyncio
async def test_quorum_after_outlier_filtering_fails_closed():
    # Only five venues answer and they split 3 vs 2 with a 5% gap: the median
    # sits in the majority, the two others are dropped, three is below quorum.
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445"}})
        m.get(KRAKEN, payload=_kraken_payload("2445"))
        m.get(GEMINI, payload={"bid": "2445", "ask": "2445"})
        m.get(BINANCE, payload={"price": "2570"})
        m.get(OKX, payload={"data": [{"last": "2570"}]})
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ReferencePriceError, match="quorum"):
                await provider.get_price("ETH", "USD", session)


@pytest.mark.asyncio
async def test_dead_bitstamp_market_is_ignored():
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445"}})
        m.get(KRAKEN, payload=_kraken_payload("2445"))
        m.get(GEMINI, payload={"bid": "2445", "ask": "2445"})
        m.get(BINANCE, payload={"price": "2445"})
        m.get(BITSTAMP, payload={"bid": "0", "ask": "0", "volume": "0.0"})
        async with aiohttp.ClientSession() as session:
            # four healthy venues, bitstamp's zero-volume ticker is not a quote
            assert await provider.get_price("ETH", "USD", session) == 2445.0


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
    provider = three_venues(cache_ttl_seconds=0)
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
    provider = three_venues(cache_ttl_seconds=60)
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
    provider = three_venues(cache_ttl_seconds=60)
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BINANCE, payload={"price": "2448.32"})
        async with aiohttp.ClientSession() as session:
            prices = await asyncio.gather(
                *(provider.get_price("ETH", "USD", session) for _ in range(20))
            )
    assert prices == [2447.34] * 20
