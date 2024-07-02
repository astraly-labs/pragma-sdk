import asyncio
import logging
import time
from typing import Any, List, Union

from aiohttp import ClientSession

from pragma.common.types.entry import SpotEntry
from pragma.common.types.pair import Pair
from pragma.offchain.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)


class UpbitFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://sg-api.upbit.com/v1/ticker"
    SOURCE: str = "UPBIT"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from Upbit")
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
        url = (
            f"{self.BASE_URL}?markets={pair.base_currency.id}-{pair.quote_currency.id}"
        )
        return url

    def _construct(self, pair: Pair, result: Any) -> SpotEntry:
        data = result[0]
        timestamp = int(time.time())
        price = float(data["trade_price"])
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(data["trade_volume"])

        logger.info("Fetched price %d for %s from Upbit", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
