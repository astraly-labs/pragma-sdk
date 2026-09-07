"""
GeckoTerminal: one batched request per network, clean errors on 429, and a
liquidity floor. The public API rate-limits after three calls in a burst and
answers a payload without `data`; a token with no reserve behind it is not a
price (sSTRK on GeckoTerminal has $0 of reserve).
"""

import json

import aiohttp
import pytest

from unittest import mock
from aioresponses import aioresponses

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetchers import GeckoTerminalFetcher
from pragma_sdk.common.fetchers.fetchers.geckoterminal import ASSET_MAPPING
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair

from tests.integration.constants import MOCK_DIR
from tests.integration.fetchers.fetcher_configs import PUBLISHER_NAME

MULTI = json.load(open(MOCK_DIR / "responses" / "gecko_multi.json"))
LUSD_USD, WBTC_USD = Pair.from_tickers("LUSD", "USD"), Pair.from_tickers("WBTC", "USD")


def _multi_url(*tickers: str) -> str:
    network = ASSET_MAPPING[tickers[0]][0]
    addresses = ",".join(hex(int(ASSET_MAPPING[t][1], 16)) for t in tickers)
    return GeckoTerminalFetcher.BASE_URL.format(network=network, addresses=addresses)


def _rate_limited(url_matcher, **kwargs):
    return {
        "status": {
            "error_code": 429,
            "error_message": "You've exceeded the Rate Limit.",
        }
    }


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_one_request_per_network():
    fetcher = GeckoTerminalFetcher([LUSD_USD, WBTC_USD], PUBLISHER_NAME)
    with aioresponses() as m:
        m.get(_multi_url("LUSD", "WBTC"), payload=MULTI)  # single-shot: one call only
        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)
    assert result == [
        SpotEntry(
            "LUSD/USD", 98898157, 12345, "GECKOTERMINAL", PUBLISHER_NAME, volume=1264558
        ),
        SpotEntry(
            "WBTC/USD",
            2580468000000,
            12345,
            "GECKOTERMINAL",
            PUBLISHER_NAME,
            volume=90241580,
        ),
    ]


@pytest.mark.asyncio
async def test_rate_limit_is_a_clean_error_for_every_pair():
    fetcher = GeckoTerminalFetcher([LUSD_USD, WBTC_USD], PUBLISHER_NAME)
    with aioresponses() as m:
        m.get(_multi_url("LUSD", "WBTC"), status=429, payload=_rate_limited(None))
        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)
    assert len(result) == 2
    assert all(isinstance(r, PublisherFetchError) and "429" in str(r) for r in result)


@pytest.mark.asyncio
async def test_thin_token_is_rejected():
    # sSTRK as GeckoTerminal reports it on 2026-09-07: a price, no reserve, no volume
    sstrk = Pair.from_tickers("SSTRK", "USD")
    fetcher = GeckoTerminalFetcher([sstrk], PUBLISHER_NAME)
    payload = {
        "data": [
            {
                "attributes": {
                    "address": ASSET_MAPPING["SSTRK"][1].lower(),
                    "price_usd": "0.02606071126",
                    "total_reserve_in_usd": "0.0",
                    "volume_usd": {"h24": "0.0"},
                }
            }
        ]
    }
    with aioresponses() as m:
        m.get(_multi_url("SSTRK"), payload=payload)
        async with aiohttp.ClientSession() as session:
            [result] = await fetcher.fetch(session)
    assert isinstance(result, PublisherFetchError)
    assert "too thin" in str(result)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_non_usd_quote_is_a_ratio_of_two_usd_prices():
    wbtc_lusd = Pair.from_tickers("WBTC", "LUSD")
    fetcher = GeckoTerminalFetcher([wbtc_lusd], PUBLISHER_NAME)
    with aioresponses() as m:
        m.get(_multi_url("WBTC", "LUSD"), payload=MULTI)
        async with aiohttp.ClientSession() as session:
            [result] = await fetcher.fetch(session)
    assert isinstance(result, SpotEntry)
    assert result.price == int(25804.68 / 0.98898157 * 10 ** wbtc_lusd.decimals())


def test_nstr_is_the_starknet_token():
    assert ASSET_MAPPING["NSTR"][0] == "starknet-alpha"
