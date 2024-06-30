import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.entry import SpotEntry
from pragma.core.types import Pair
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class CoinbaseFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.coinbase.com/v2/exchange-rates?currency="
    SOURCE: str = "COINBASE"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from Coinbase")
            result = await resp.json()
            return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = self.BASE_URL + pair.base_currency.id
        return url

    def _construct(self, pair: Pair, result) -> Union[SpotEntry, PublisherFetchError]:
        if pair[0] in result["data"]["rates"]:
            rate = float(result["data"]["rates"][pair.base_currency.id])
            price = 1 / rate
            price_int = int(price * (10 ** pair.decimals()))
            timestamp = int(time.time())

            logger.info("Fetched price %d for %s from Coinbase", price, pair.id)

            return SpotEntry(
                pair_id=pair.id,
                price=price_int,
                timestamp=timestamp,
                source=self.SOURCE,
                publisher=self.publisher,
            )

        return PublisherFetchError(f"No entry found for {pair.id} from Coinbase")
