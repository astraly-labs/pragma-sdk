import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.types import Pair
from pragma.publisher.client import PragmaOnChainClient
from pragma.core.entry import SpotEntry
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class AscendexFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://ascendex.com/api/pro/v1/spot/ticker"
    client: PragmaOnChainClient
    SOURCE: str = "ASCENDEX"
    publisher: str

    def __init__(self, pairs: List[Pair], publisher, client=None):
        self.pairs = pairs
        self.publisher = publisher
        self.client = client or PragmaOnChainClient(network="mainnet")

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        if pair.quote_currency.id == "USD":
            pair = Pair(pair.base_currency, ...)  # TODO: add USDT
        else:
            usdt_price = 1

        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Ascendex")

            result = await resp.json()
            if result["code"] == 100002 and result["reason"] == "DATA_NOT_AVAILABLE":
                return PublisherFetchError(f"No data found for {pair} from Ascendex")

            return self._construct(pair, result, usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        # Fetching usdt price (done one time)
        usdt_price = await self.get_stable_price("USDT")
        for pair in self.pairs:
            entries.append(
                asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
            )
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}?symbol={pair.base_currency.id}/{pair.quote_currency.id}"
        return url

    def _construct(self, pair: Pair, result, usdt_price) -> SpotEntry:
        data = result["data"]
        timestamp = int(time.time())
        ask = float(data["ask"][0])
        bid = float(data["bid"][0])
        price = (ask + bid) / (2.0 * usdt_price)
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(data["volume"])

        logger.info("Fetched price %d for %s from Ascendex", price, pair)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=int(volume),
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=int(volume),
        )
