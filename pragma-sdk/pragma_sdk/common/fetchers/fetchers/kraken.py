import time
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair

logger = get_pragma_sdk_logger()

# Kraken still uses legacy codes for a few assets in its pair names.
KRAKEN_ASSET_ALIASES: Dict[str, str] = {"BTC": "XBT", "DOGE": "XDG"}


class KrakenFetcher(FetcherInterfaceT):
    """
    Kraken spot markets, quoted in fiat USD (no USDT hop).

    One batched Ticker request per fetch: Kraken rejects the whole batch on a
    single unknown pair, so the listed markets are read from AssetPairs first
    (cached for MARKETS_TTL_S) and only those are requested.
    """

    BASE_URL: str = "https://api.kraken.com/0/public"
    SOURCE: str = "KRAKEN"
    MARKETS_TTL_S: int = 3600

    # wsname ("XMR/USD") -> (result key "XXMRZUSD", altname "XMRUSD")
    _markets: Optional[Dict[str, tuple[str, str]]] = None
    _markets_loaded_at: float = 0.0

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        return await self._fetch_many(self.pairs, session)

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        return (await self._fetch_many([pair], session))[0]

    def format_url(self, pair: Pair) -> str:
        return f"{self.BASE_URL}/Ticker?pair={self._altname(pair)}"

    @staticmethod
    def _wsname(pair: Pair) -> str:
        base = KRAKEN_ASSET_ALIASES.get(pair.base_currency.id, pair.base_currency.id)
        quote = KRAKEN_ASSET_ALIASES.get(pair.quote_currency.id, pair.quote_currency.id)
        return f"{base}/{quote}"

    def _altname(self, pair: Pair) -> str:
        return self._wsname(pair).replace("/", "")

    async def _load_markets(self, session: ClientSession) -> Dict[str, tuple[str, str]]:
        if (
            self._markets is not None
            and time.time() - self._markets_loaded_at < self.MARKETS_TTL_S
        ):
            return self._markets
        async with session.get(f"{self.BASE_URL}/AssetPairs") as resp:
            if resp.status != 200:
                raise PublisherFetchError(f"Kraken AssetPairs status {resp.status}")
            data = await resp.json()
        if data.get("error"):
            raise PublisherFetchError(f"Kraken AssetPairs: {data['error']}")
        # A market in cancel_only / post_only cannot trade: its last price is a
        # frozen number, not a price.
        self._markets = {
            info["wsname"]: (key, info["altname"])
            for key, info in data["result"].items()
            if info.get("status") == "online" and "wsname" in info
        }
        self._markets_loaded_at = time.time()
        return self._markets

    async def _fetch_many(
        self, pairs: List[Pair], session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        try:
            markets = await self._load_markets(session)
        except (PublisherFetchError, Exception) as e:
            return [
                PublisherFetchError(f"Kraken markets unavailable: {e}") for _ in pairs
            ]

        listed = {
            pair: markets[self._wsname(pair)]
            for pair in pairs
            if self._wsname(pair) in markets
        }
        results: Dict[Pair, Entry | PublisherFetchError] = {
            pair: PublisherFetchError(f"No data found for {pair} from Kraken")
            for pair in pairs
        }
        if listed:
            altnames = ",".join(altname for _, altname in listed.values())
            try:
                async with session.get(
                    f"{self.BASE_URL}/Ticker?pair={altnames}"
                ) as resp:
                    if resp.status != 200:
                        raise PublisherFetchError(f"Kraken Ticker status {resp.status}")
                    data = await resp.json()
                if data.get("error"):
                    raise PublisherFetchError(f"Kraken Ticker: {data['error']}")
                for pair, (key, _) in listed.items():
                    ticker = data["result"].get(key)
                    if ticker is None:
                        continue
                    results[pair] = self._construct(pair, ticker)
            except Exception as e:
                for pair in listed:
                    results[pair] = PublisherFetchError(
                        f"No data found for {pair} from Kraken: {e}"
                    )
        return [results[pair] for pair in pairs]

    def _construct(self, pair: Pair, ticker: Any) -> SpotEntry | PublisherFetchError:
        # a/b = [price, whole lot volume, lot volume], c = [last trade, lot],
        # v = [today, last 24h] base volume, p = [today, last 24h] VWAP.
        volume_24h = float(ticker["v"][1])
        if volume_24h <= 0:
            return PublisherFetchError(
                f"No data found for {pair} from Kraken: market has no 24h volume"
            )
        spread_error = self.reject_wide_spread(
            pair, float(ticker["b"][0]), float(ticker["a"][0])
        )
        if spread_error is not None:
            return spread_error
        price = float(ticker["c"][0])
        price_int = int(price * (10 ** pair.decimals()))
        quote_volume = volume_24h * float(ticker["p"][1])

        logger.debug("Fetched price %d for %s from Kraken", price_int, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=quote_volume,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )
