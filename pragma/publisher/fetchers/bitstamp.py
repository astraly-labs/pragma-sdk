import asyncio
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.entry import SpotEntry
from pragma.core.types import Pair
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class BitstampFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://www.bitstamp.net/api/v2/ticker"
    SOURCE: str = "BITSTAMP"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bitstamp"
                )

            return self._construct(pair, await resp.json())

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []

        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}/{pair.base_currency.id.lower()}{pair.quote_currency.id.lower()}"
        return url

    def _construct(self, pair: Pair, result) -> SpotEntry:
        timestamp = int(result["timestamp"])
        price = float(result["last"])
        price_int = int(price * (10 ** pair.decimals()))

        logger.info("Fetched price %d for %s from Bitstamp", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
