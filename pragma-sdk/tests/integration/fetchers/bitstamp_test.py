import aiohttp
import pytest

from unittest import mock
from aioresponses import aioresponses

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetchers import BitstampFetcher
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair

from tests.integration.fetchers.fetcher_configs import PUBLISHER_NAME

# Real Bitstamp answers on 2026-09-04: strkusd is a dead market (zero volume,
# `last` ~31% above the market), btcusd is live.
DEAD_STRK = {
    "timestamp": "1788524503",
    "open": "0.000000",
    "high": "0.000000",
    "low": "0.000000",
    "last": "0.035400",
    "volume": "0.0",
    "vwap": "0.000000",
    "bid": "0.000000",
    "ask": "0.035900",
}
LIVE_BTC = {
    "timestamp": "1788524502",
    "open": "81265.00",
    "high": "82280.62",
    "low": "77905.68",
    "last": "81140.76",
    "volume": "2521.59885253",
    "vwap": "80754.28",
    "bid": "81140.75",
    "ask": "81140.76",
}


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_bitstamp_rejects_zero_volume_market():
    strk, btc = Pair.from_tickers("STRK", "USD"), Pair.from_tickers("BTC", "USD")
    fetcher = BitstampFetcher([strk, btc], PUBLISHER_NAME)
    with aioresponses() as mocked:
        mocked.get(fetcher.format_url(strk), status=200, payload=DEAD_STRK)
        mocked.get(fetcher.format_url(btc), status=200, payload=LIVE_BTC)
        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

    by_type = {type(r): r for r in result}
    assert by_type[PublisherFetchError] == PublisherFetchError(
        "No data found for STRK/USD from Bitstamp: market has no 24h volume"
    )
    assert by_type[SpotEntry] == SpotEntry(
        "BTC/USD", int(81140.76 * 10**8), 12345, "BITSTAMP", PUBLISHER_NAME
    )
