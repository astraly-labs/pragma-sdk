"""
Thin markets are not prices. A CEX quote whose bid/ask spread is wider than
MAX_BID_ASK_SPREAD (2%) is rejected. Huobi STRK/USDT sat at 2-3% and printed
up to -8% off the market for two days.
"""

import aiohttp
import pytest

from unittest import mock
from aioresponses import aioresponses

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetchers import (
    BinanceFetcher,
    HuobiFetcher,
    LbankFetcher,
)
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair

from tests.integration.fetchers.fetcher_configs import PUBLISHER_NAME

STRK_USD = Pair.from_tickers("STRK", "USD")
STRK_USDT = Pair.from_tickers("STRK", "USDT")

# Real Huobi answer of 2026-09-07: bid 0.0298, ask 0.0305, spread 2.32%.
HUOBI_THIN = {
    "status": "ok",
    "tick": {"bid": [0.0298, 100], "ask": [0.0305, 100], "vol": 1000},
}
HUOBI_TIGHT = {
    "status": "ok",
    "tick": {"bid": [0.03073, 100], "ask": [0.03074, 100], "vol": 1000},
}


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_huobi_thin_market_is_rejected():
    fetcher = HuobiFetcher([STRK_USD], PUBLISHER_NAME)
    with aioresponses() as m:
        m.get(fetcher.format_url(STRK_USDT), payload=HUOBI_THIN)
        async with aiohttp.ClientSession() as session:
            [result] = await fetcher.fetch(session)
    assert isinstance(result, PublisherFetchError)
    assert "spread 2.32%" in str(result) and "too thin" in str(result)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_huobi_tight_market_is_published():
    fetcher = HuobiFetcher([STRK_USD], PUBLISHER_NAME)
    with aioresponses() as m:
        m.get(fetcher.format_url(STRK_USDT), payload=HUOBI_TIGHT)
        async with aiohttp.ClientSession() as session:
            [result] = await fetcher.fetch(session)
    assert isinstance(result, SpotEntry)
    assert result.price == int((0.03073 + 0.03074) / 2 * 10**8)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_binance_spread_guard_and_bad_book():
    fetcher = BinanceFetcher([STRK_USD], PUBLISHER_NAME)
    url = fetcher.format_url(STRK_USDT)
    for payload, ok in [
        ({"bidPrice": "0.03073", "askPrice": "0.03074"}, True),
        ({"bidPrice": "0.0298", "askPrice": "0.0305"}, False),
        ({"bidPrice": "0.00000000", "askPrice": "0.00000000"}, False),
    ]:
        with aioresponses() as m:
            m.get(url, payload=payload)
            async with aiohttp.ClientSession() as session:
                [result] = await fetcher.fetch(session)
        assert isinstance(result, SpotEntry) is ok, payload


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_lbank_payload_without_data_is_a_clean_error():
    fetcher = LbankFetcher([STRK_USD], PUBLISHER_NAME)
    with aioresponses() as m:
        m.get(
            fetcher.format_url(STRK_USDT),
            payload={"result": "false", "error_code": 10001, "msg": "symbol error"},
        )
        # the hop path then asks for STRK/USDT and USD/USDT: unsupported too
        m.get(fetcher.format_url(STRK_USDT), payload={"code": 1})
        async with aiohttp.ClientSession() as session:
            [result] = await fetcher.fetch(session)
    assert isinstance(result, PublisherFetchError)
