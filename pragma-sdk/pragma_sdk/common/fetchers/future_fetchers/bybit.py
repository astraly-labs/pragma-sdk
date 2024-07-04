import asyncio
import json
import logging
from typing import Any, List, Union

from aiohttp import ClientSession

from pragma_sdk.common.types.entry import FutureEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)


class ByBitFutureFetcher(FetcherInterfaceT):
    BASE_URL: str = (
        "https://api.bybit.com/derivatives/v3/public/tickers?category=linear&symbol="
    )
    SOURCE: str = "BYBIT"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[FutureEntry, PublisherFetchError]:
        url = self.format_url(pair)

        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from BYBIT")

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"BYBIT: Unexpected content type: {content_type}")

            if (
                result["retCode"] == "51001"
                or result["retMsg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(f"No data found for {pair} from BYBIT")

            return self._construct(pair, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[FutureEntry, PublisherFetchError]]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}{pair.base_currency.id}{pair.quote_currency.id}"
        return url

    def _construct(self, pair: Pair, result: Any) -> FutureEntry:
        data = result["result"]["list"][0]
        decimals = pair.decimals()
        timestamp = int(int(result["time"]) / 1000)

        price = float(data["lastPrice"])
        price_int = int(price * (10**decimals))

        volume = float(data["volume24h"])
        expiry_timestamp = int(data["deliveryTime"])

        logger.info("Fetched future for %s from BYBIT", (pair.id))

        return FutureEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            expiry_timestamp=expiry_timestamp,
        )
