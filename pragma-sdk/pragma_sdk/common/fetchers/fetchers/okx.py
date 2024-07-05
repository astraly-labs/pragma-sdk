import asyncio
import json
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.fetchers.hop_handler import HopHandler

logger = logging.getLogger(__name__)


class OkxFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://okx.com/api/v5/market/ticker"
    SOURCE: str = "OKX"

    hop_handler = HopHandler(
        hopped_currencies={
            "USD": "USDT",
        }
    )

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        new_pair = self.hop_handler.get_hop_pair(pair) or pair
        url = self.format_url(new_pair)

        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from OKX")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"OKX: Unexpected content type: {content_type}")

            if (
                result["code"] == "51001"
                or result["msg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(f"No data found for {pair} from OKX")

            return self._construct(pair, result, usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for pair in self.pairs:
            entries.append(
                asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
            )
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}?instId={pair.base_currency.id}-{pair.quote_currency.id}-SWAP"
        return url

    def _construct(self, pair: Pair, result, usdt_price=1) -> SpotEntry:
        data = result["data"][0]

        timestamp = int(int(data["ts"]) / 1000)
        price = float(data["last"]) / usdt_price
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(data["volCcy24h"])

        logger.info("Fetched price %d for %s from OKX", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )