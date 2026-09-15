import asyncio

import aiohttp
import pytest

from aioresponses import aioresponses

from pragma_sdk.common.fetchers.handlers.reference_price import (
    STABLE_CHECK_SOURCES,
    USDT_QUOTED_SOURCES,
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
    _mock_usdt(m, 1.0)


def four_venues(**kwargs) -> ReferencePriceProvider:
    """Coinbase, Kraken, Bitstamp, Binance: the compact fixture at quorum 4."""
    subset = tuple(
        s
        for s in DEFAULT_SOURCES
        if s[0] in ("coinbase", "kraken", "bitstamp", "binance")
    )
    return ReferencePriceProvider(sources=subset, **kwargs)


def _mock_four(m, coinbase: str, kraken: str, bitstamp: str, binance: str):
    m.get(COINBASE, payload={"data": {"amount": coinbase}})
    m.get(KRAKEN, payload=_kraken_payload(kraken))
    m.get(BITSTAMP, payload={"bid": bitstamp, "ask": bitstamp, "volume": "100"})
    m.get(BINANCE, payload={"price": binance})
    _mock_usdt(m, 1.0)


def test_default_provider_has_nine_independent_venues():
    names = [name for name, _ in DEFAULT_SOURCES]
    assert len(names) == 9 and len(set(names)) == 9
    assert ReferencePriceProvider().quorum == 4
    assert ReferencePriceProvider().stable_quorum == 4
    stable = [name for name, _ in STABLE_CHECK_SOURCES]
    assert len(stable) == 7 and not USDT_QUOTED_SOURCES & set(stable)


@pytest.mark.asyncio
async def test_median_of_independent_sources():
    provider = four_venues()
    with aioresponses() as m:
        _mock_four(m, "2445.29", "2447.34", "2447.34", "2448.32")
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
    provider = four_venues()
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2445.29"}})
        m.get(KRAKEN, status=503)
        m.get(BITSTAMP, payload={"bid": "2447", "ask": "2447", "volume": "100"})
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
        _mock_usdt(m, 1.0)
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
        _mock_usdt(m, 1.0)
        async with aiohttp.ClientSession() as session:
            # four healthy venues, bitstamp's zero-volume ticker is not a quote
            assert await provider.get_price("ETH", "USD", session) == 2445.0


@pytest.mark.asyncio
async def test_stables_are_one_without_any_request():
    provider = ReferencePriceProvider()
    with aioresponses():
        # no mocked endpoint: any HTTP call would raise
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USD", "USDPLUS", session) == 1.0
            assert await provider.get_price("USDPLUS", "USD", session) == 1.0


@pytest.mark.asyncio
async def test_cross_quote_uses_both_usd_references():
    provider = four_venues(cache_ttl_seconds=0)
    with aioresponses() as m:
        for url, payload in [
            (COINBASE, {"data": {"amount": "2000"}}),
            (KRAKEN, _kraken_payload("2000")),
            (BITSTAMP, {"bid": "2000", "ask": "2000", "volume": "100"}),
            (BINANCE, {"price": "2000"}),
            (
                "https://www.bitstamp.net/api/v2/ticker/btcusd/",
                {"bid": "80000", "ask": "80000", "volume": "100"},
            ),
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
        _mock_usdt(m, 1.0)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "BTC", session) == 0.025


@pytest.mark.asyncio
async def test_cache_shares_one_lookup():
    provider = four_venues(cache_ttl_seconds=60)
    with aioresponses() as m:
        _mock_four(m, "2445.29", "2447.34", "2447.34", "2448.32")
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
    provider = four_venues(cache_ttl_seconds=60)
    with aioresponses() as m:
        _mock_four(m, "2445.29", "2447.34", "2447.34", "2448.32")
        async with aiohttp.ClientSession() as session:
            prices = await asyncio.gather(
                *(provider.get_price("ETH", "USD", session) for _ in range(20))
            )
    assert prices == [2447.34] * 20


# ------------------------------------------------------------ stablecoin peg

USDT_KRAKEN = "https://api.kraken.com/0/public/Ticker?pair=USDTUSD"
USDT_COINBASE = "https://api.coinbase.com/v2/prices/USDT-USD/spot"
USDT_BITSTAMP = "https://www.bitstamp.net/api/v2/ticker/usdtusd/"
USDT_BITFINEX = "https://api-pub.bitfinex.com/v2/ticker/tUSTUSD"


USDT_GEMINI = "https://api.gemini.com/v1/pubticker/usdtusd"
USDT_BITGET = "https://api.bitget.com/api/v2/spot/market/tickers?symbol=USDTUSD"
USDT_CRYPTOCOM = (
    "https://api.crypto.com/exchange/v1/public/get-tickers?instrument_name=USDT_USD"
)


def _mock_usdt(m, price: float, venues: int = 7):
    """Mock the first `venues` peg venues at `price`; the rest stay unmocked."""
    p = str(price)
    mocks = [
        (USDT_KRAKEN, {"error": [], "result": {"USDTZUSD": {"c": [p, "1"]}}}),
        (USDT_COINBASE, {"data": {"amount": p}}),
        (USDT_BITSTAMP, {"bid": p, "ask": p, "volume": "1000"}),
        (USDT_BITFINEX, [price, 1.0, price, 1.0]),
        (USDT_GEMINI, {"bid": p, "ask": p}),
        (USDT_BITGET, {"code": "00000", "data": [{"bidPr": p, "askPr": p}]}),
        (USDT_CRYPTOCOM, {"code": 0, "result": {"data": [{"b": p, "k": p}]}}),
    ]
    for url, payload in mocks[:venues]:
        m.get(url, payload=payload)


@pytest.mark.asyncio
async def test_stable_is_converted_at_its_measured_price():
    provider = ReferencePriceProvider()
    with aioresponses() as m:
        _mock_usdt(m, 0.9985)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USDT", "USD", session) == 0.9985


@pytest.mark.asyncio
async def test_material_depeg_is_converted_not_hidden():
    from unittest import mock

    provider = ReferencePriceProvider()
    with (
        aioresponses() as m,
        mock.patch(
            "pragma_sdk.common.fetchers.handlers.reference_price.logger"
        ) as logger,
    ):
        _mock_usdt(m, 0.93)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USDT", "USD", session) == 0.93
    assert any("DEPEG" in str(c.args[0]) for c in logger.warning.call_args_list)


@pytest.mark.asyncio
async def test_unmeasurable_peg_reuses_a_fresh_verified_value():
    provider = ReferencePriceProvider(cache_ttl_seconds=0)
    with aioresponses() as m:
        _mock_usdt(m, 0.9985)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USDT", "USD", session) == 0.9985
    with aioresponses() as m:
        m.get(USDT_KRAKEN, status=503)  # every venue down
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USDT", "USD", session) == 0.9985


@pytest.mark.asyncio
async def test_unmeasurable_peg_with_no_fresh_value_fails_closed():
    provider = ReferencePriceProvider(cache_ttl_seconds=0, stable_max_age_seconds=0)
    with aioresponses() as m:
        _mock_usdt(m, 0.9985)
        async with aiohttp.ClientSession() as session:
            await provider.get_price("USDT", "USD", session)
    with aioresponses() as m:
        m.get(USDT_KRAKEN, status=503)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ReferencePriceError, match="unmeasurable"):
                await provider.get_price("USDT", "USD", session)


@pytest.mark.asyncio
async def test_usd_and_usdplus_never_query_venues():
    provider = ReferencePriceProvider()
    with aioresponses():
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USD", "USD", session) == 1.0
            assert await provider.get_price("USDPLUS", "USD", session) == 1.0


@pytest.mark.asyncio
async def test_reference_reuses_a_fresh_verified_value_when_venues_fail():
    # 5 of 9 venues timing out must not drop WSTETH/LBTC/... when ETH/USD
    # was verified moments ago.
    provider = four_venues(cache_ttl_seconds=0)
    with aioresponses() as m:
        _mock_four(m, "2445.29", "2447.34", "2447.34", "2448.32")
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "USD", session) == 2447.34
    with aioresponses() as m:
        m.get(COINBASE, status=503)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "USD", session) == 2447.34


@pytest.mark.asyncio
async def test_venue_failures_are_logged_with_their_type():
    from unittest import mock

    provider = four_venues()
    with (
        aioresponses() as m,
        mock.patch(
            "pragma_sdk.common.fetchers.handlers.reference_price.logger"
        ) as logger,
    ):
        m.get(COINBASE, exception=TimeoutError())
        m.get(KRAKEN, payload=_kraken_payload("2447.34"))
        m.get(BITSTAMP, payload={"bid": "2447.34", "ask": "2447.34", "volume": "1"})
        m.get(BINANCE, payload={"price": "2448.32"})
        _mock_usdt(m, 1.0)
        async with aiohttp.ClientSession() as session:
            try:
                await provider.get_price("ETH", "USD", session)
            except ReferencePriceError:
                pass  # three venues left: below quorum, the log is what matters
    logged = [c.args for c in logger.warning.call_args_list]
    assert any("TimeoutError" in str(args) for args in logged)


@pytest.mark.asyncio
async def test_peg_survives_three_venues_down():
    provider = ReferencePriceProvider(cache_ttl_seconds=0)
    with aioresponses() as m:
        _mock_usdt(m, 0.999, venues=4)  # gemini, bitget, crypto.com unmocked
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("USDT", "USD", session) == 0.999


@pytest.mark.asyncio
async def test_peg_needs_four_agreeing_venues():
    provider = ReferencePriceProvider(cache_ttl_seconds=0, stable_max_age_seconds=0)
    with aioresponses() as m:
        _mock_usdt(m, 0.999, venues=3)
        async with aiohttp.ClientSession() as session:
            with pytest.raises(ReferencePriceError, match="quorum is 4"):
                await provider.get_price("USDT", "USD", session)


@pytest.mark.asyncio
async def test_coinbase_par_quote_does_not_count_for_usdc():
    # Coinbase returns a constant 1 for USDC-USD: it must not be a peg venue.
    provider = ReferencePriceProvider(cache_ttl_seconds=0, stable_max_age_seconds=0)
    with aioresponses() as m:
        m.get(
            "https://api.coinbase.com/v2/prices/USDC-USD/spot",
            payload={"data": {"amount": "1"}},
        )
        for url, payload in [
            (
                "https://api.kraken.com/0/public/Ticker?pair=USDCUSD",
                {"error": [], "result": {"USDCUSD": {"c": ["0.97", "1"]}}},
            ),
            (
                "https://www.bitstamp.net/api/v2/ticker/usdcusd/",
                {"bid": "0.97", "ask": "0.97", "volume": "10"},
            ),
            ("https://api-pub.bitfinex.com/v2/ticker/tUDCUSD", [0.97, 1, 0.97, 1]),
        ]:
            m.get(url, payload=payload)
        async with aiohttp.ClientSession() as session:
            # three real venues at 0.97 + coinbase's fake 1.0: not a quorum
            with pytest.raises(ReferencePriceError, match="quorum is 4"):
                await provider.get_price("USDC", "USD", session)


@pytest.mark.asyncio
@pytest.mark.parametrize("usdt_usd", [0.9, 1.1])
async def test_usdt_quotes_are_converted_before_the_median(usdt_usd):
    # Three USD venues and four USDT venues: taken at par, the USDT side would
    # win the median and the correct USD quotes would be dropped as outliers.
    provider = ReferencePriceProvider()
    eth_usdt, eth_usd = 2000.0, 2000.0 * usdt_usd
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": str(eth_usd)}})
        m.get(KRAKEN, payload=_kraken_payload(str(eth_usd)))
        m.get(GEMINI, payload={"bid": str(eth_usd), "ask": str(eth_usd)})
        m.get(BINANCE, payload={"price": str(eth_usdt)})
        m.get(OKX, payload={"data": [{"last": str(eth_usdt)}]})
        m.get(BYBIT, payload={"result": {"list": [{"lastPrice": str(eth_usdt)}]}})
        m.get(KUCOIN, payload={"data": {"price": str(eth_usdt)}})
        _mock_usdt(m, usdt_usd)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "USD", session) == eth_usd


@pytest.mark.asyncio
@pytest.mark.parametrize("usd_venues", [3, 4])
async def test_unverified_usdt_quotes_are_left_out(usd_venues):
    provider = ReferencePriceProvider(stable_max_age_seconds=0)
    with aioresponses() as m:
        m.get(COINBASE, payload={"data": {"amount": "2000"}})
        m.get(KRAKEN, payload=_kraken_payload("2000"))
        m.get(GEMINI, payload={"bid": "2000", "ask": "2000"})
        if usd_venues == 4:
            m.get(BITSTAMP, payload={"bid": "2000", "ask": "2000", "volume": "1"})
        for url, payload in [
            (BINANCE, {"price": "2200"}),
            (OKX, {"data": [{"last": "2200"}]}),
            (BYBIT, {"result": {"list": [{"lastPrice": "2200"}]}}),
            (KUCOIN, {"data": {"price": "2200"}}),
        ]:
            m.get(url, payload=payload)
        # no peg venue answers: the four USDT quotes must not be taken at par
        async with aiohttp.ClientSession() as session:
            if usd_venues == 4:
                assert await provider.get_price("ETH", "USD", session) == 2000.0
            else:
                with pytest.raises(ReferencePriceError, match="quorum is 4"):
                    await provider.get_price("ETH", "USD", session)


@pytest.mark.asyncio
async def test_converted_reference_expires_with_its_usdt_conversion(monkeypatch):
    now = 1000.0
    monkeypatch.setattr(
        "pragma_sdk.common.fetchers.handlers.reference_price.time.monotonic",
        lambda: now,
    )
    provider = ReferencePriceProvider(cache_ttl_seconds=0)
    with aioresponses() as m:
        _mock_usdt(m, 0.9)
        async with aiohttp.ClientSession() as session:
            await provider.get_price("USDT", "USD", session)

    now += 200
    with aioresponses() as m:
        # only USDT venues answer; the conversion they use is 200s old
        for url, payload in [
            (BINANCE, {"price": "2000"}),
            (OKX, {"data": [{"last": "2000"}]}),
            (BYBIT, {"result": {"list": [{"lastPrice": "2000"}]}}),
            (KUCOIN, {"data": {"price": "2000"}}),
        ]:
            m.get(url, payload=payload)
        async with aiohttp.ClientSession() as session:
            assert await provider.get_price("ETH", "USD", session) == 1800.0

    now += 101
    with aioresponses():
        async with aiohttp.ClientSession() as session:
            # the reused ETH/USD must age with the 301s-old USDT/USD it embeds
            with pytest.raises(ReferencePriceError):
                await provider.get_price("ETH", "USD", session)
