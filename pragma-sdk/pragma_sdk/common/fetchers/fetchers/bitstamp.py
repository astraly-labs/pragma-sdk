import asyncio
import time
from typing import Any, List

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


class BitstampFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://www.bitstamp.net/api/v2/ticker"
    SOURCE: str = "BITSTAMP"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> SpotEntry | PublisherFetchError:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Bitstamp")

            return self._construct(pair, await resp.json())

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        entries = [
            asyncio.ensure_future(self.fetch_pair(pair, session)) for pair in self.pairs
        ]
        return list(await asyncio.gather(*entries, return_exceptions=True))

    def format_url(self, pair: Pair) -> str:
        url = f"{self.BASE_URL}/{pair.base_currency.id.lower()}{pair.quote_currency.id.lower()}"
        return url

    def _construct(self, pair: Pair, result: Any) -> SpotEntry | PublisherFetchError:
        if not isinstance(result, dict):
            # Unknown market: Bitstamp answers 200 with the list of all tickers.
            return PublisherFetchError(f"No data found for {pair} from Bitstamp")
        # Bitstamp keeps listing markets nobody trades anymore (e.g. strkusd):
        # the ticker still answers 200 with a stale `last` and a zero 24h volume.
        # STRK/USD sat 31% above the market that way. A market with no volume
        # has no price.
        volume = float(result.get("volume", 0) or 0)
        if volume <= 0:
            return PublisherFetchError(
                f"No data found for {pair} from Bitstamp: market has no 24h volume"
            )
        timestamp = int(time.time())
        spread_error = self.reject_wide_spread(
            pair, float(result["bid"]), float(result["ask"])
        )
        if spread_error is not None:
            return spread_error
        price = float(result["last"])
        price_int = int(price * (10 ** pair.decimals()))

        logger.debug("Fetched price %d for %s from Bitstamp", price_int, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
