import asyncio
import json
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.entry import SpotEntry
from pragma.core.types import Pair
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class CexFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://cex.io/api/ticker"
    SOURCE: str = "CEX"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from CEX")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"CEX: Unexpected content type: {content_type}")

            if "error" in result and result["error"] == "Invalid Symbols Pair":
                return PublisherFetchError(f"No data found for {pair.id} from CEX")

            return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}/{pair.base_currency.id}/{pair.quote_currency.id}"
        return url

    def _construct(self, pair: Pair, result) -> SpotEntry:
        timestamp = int(result["timestamp"])
        price = float(result["last"])
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(result["volume"])

        logger.info("Fetched price %d for %s from CEX", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            volume=int(volume),
            source=self.SOURCE,
            publisher=self.publisher,
        )
