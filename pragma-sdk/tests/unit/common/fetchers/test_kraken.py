import pytest

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetchers.kraken import KrakenFetcher
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.utils import felt_to_str

ASSET_PAIRS_URL = "https://api.kraken.com/0/public/AssetPairs"
TICKER_URL = "https://api.kraken.com/0/public/Ticker?pair="


class _Response:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class FakeSession:
    def __init__(self, responses):
        self._responses = dict(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        status, payload = self._responses[url]
        return _Response(status, payload)


def ticker(last, bid, ask, volume_24h="100", vwap_24h=None):
    return {
        "a": [ask, "1", "1.000"],
        "b": [bid, "1", "1.000"],
        "c": [last, "0.1"],
        "v": ["10", volume_24h],
        "p": ["0", vwap_24h or last],
        "t": [10, 100],
    }


ASSET_PAIRS = {
    "error": [],
    "result": {
        "LINKUSD": {"altname": "LINKUSD", "wsname": "LINK/USD", "status": "online"},
        "XXBTZUSD": {"altname": "XBTUSD", "wsname": "XBT/USD", "status": "online"},
        "UNIUSD": {"altname": "UNIUSD", "wsname": "UNI/USD", "status": "online"},
        "STRKUSD": {
            "altname": "STRKUSD",
            "wsname": "STRK/USD",
            "status": "cancel_only",
        },
    },
}


def _fetcher(pairs):
    fetcher = KrakenFetcher.__new__(KrakenFetcher)
    fetcher.pairs = pairs
    fetcher.publisher = "TEST"
    fetcher.headers = {}
    return fetcher


@pytest.mark.asyncio
async def test_batches_listed_pairs_and_rejects_unlisted_ones():
    link = Pair.from_tickers("LINK", "USD")
    btc = Pair.from_tickers("BTC", "USD")
    lords = Pair.from_tickers("LORDS", "USD")
    strk = Pair.from_tickers("STRK", "USD")
    session = FakeSession(
        {
            ASSET_PAIRS_URL: (200, ASSET_PAIRS),
            TICKER_URL + "LINKUSD,XBTUSD": (
                200,
                {
                    "error": [],
                    "result": {
                        "LINKUSD": ticker("12.55", "12.54", "12.56"),
                        "XXBTZUSD": ticker("79000.0", "78999.0", "79001.0"),
                    },
                },
            ),
        }
    )

    results = await _fetcher([link, btc, lords, strk]).fetch(session)

    assert session.calls == [ASSET_PAIRS_URL, TICKER_URL + "LINKUSD,XBTUSD"]
    assert isinstance(results[0], SpotEntry)
    assert results[0].price == int(12.55 * 10**8)
    assert felt_to_str(results[0].base.source) == "KRAKEN"
    assert isinstance(results[1], SpotEntry)
    assert results[1].price == int(79000.0 * 10**8)
    # Not on Kraken at all, and listed but cancel_only: no price, no request.
    assert isinstance(results[2], PublisherFetchError)
    assert isinstance(results[3], PublisherFetchError)


@pytest.mark.asyncio
async def test_markets_are_cached_between_fetches():
    link = Pair.from_tickers("LINK", "USD")
    payload = {"error": [], "result": {"LINKUSD": ticker("12.5", "12.4", "12.6")}}
    session = FakeSession(
        {ASSET_PAIRS_URL: (200, ASSET_PAIRS), TICKER_URL + "LINKUSD": (200, payload)}
    )
    fetcher = _fetcher([link])

    await fetcher.fetch(session)
    await fetcher.fetch(session)

    assert session.calls.count(ASSET_PAIRS_URL) == 1


@pytest.mark.asyncio
async def test_dead_market_and_wide_spread_are_rejected():
    link = Pair.from_tickers("LINK", "USD")
    uni = Pair.from_tickers("UNI", "USD")
    session = FakeSession(
        {
            ASSET_PAIRS_URL: (200, ASSET_PAIRS),
            TICKER_URL + "LINKUSD,UNIUSD": (
                200,
                {
                    "error": [],
                    "result": {
                        "LINKUSD": ticker("12.5", "12.4", "12.6", volume_24h="0"),
                        "UNIUSD": ticker("7.0", "6.6", "7.4"),
                    },
                },
            ),
        }
    )

    no_volume, wide = await _fetcher([link, uni]).fetch(session)

    assert isinstance(no_volume, PublisherFetchError)
    assert "no 24h volume" in str(no_volume)
    assert isinstance(wide, PublisherFetchError)
    assert "spread" in str(wide)


@pytest.mark.asyncio
async def test_api_error_fails_every_pair_without_raising():
    link = Pair.from_tickers("LINK", "USD")
    session = FakeSession(
        {
            ASSET_PAIRS_URL: (200, ASSET_PAIRS),
            TICKER_URL + "LINKUSD": (200, {"error": ["EAPI:Rate limit exceeded"]}),
        }
    )

    (result,) = await _fetcher([link]).fetch(session)

    assert isinstance(result, PublisherFetchError)
    assert "Rate limit" in str(result)


@pytest.mark.asyncio
async def test_markets_unavailable_fails_closed():
    session = FakeSession({ASSET_PAIRS_URL: (503, {})})

    (result,) = await _fetcher([Pair.from_tickers("LINK", "USD")]).fetch(session)

    assert isinstance(result, PublisherFetchError)
