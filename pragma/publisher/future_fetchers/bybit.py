import asyncio
import json
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaFutureAsset
from pragma.core.entry import FutureEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class ByBitFutureFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://api.bybit.com/derivatives/v3/public/tickers?category=linear&symbol="
    )
    SOURCE: str = "BYBIT"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaFutureAsset, session: ClientSession
    ) -> Union[FutureEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = self.format_url(pair[0], pair[1])

        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from BYBIT"
                )

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
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from BYBIT"
                )

            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[FutureEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "FUTURE":
                logger.debug("Skipping BYBIT for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}{quote_asset}{base_asset}"
        return url

    def _construct(self, asset, result) -> FutureEntry:
        pair = asset["pair"]
        data = result["result"]["list"][0]
        timestamp = int(int(result["time"]) / 1000)
        price = float(data["lastPrice"])
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(data["volume24h"]) / 10 ** asset["decimals"]
        expiry_timestamp = int(data["deliveryTime"])
        logger.info("Fetched future for %s from BYBIT", ("/".join(pair)))

        return FutureEntry(
            pair_id=pair_id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            expiry_timestamp=expiry_timestamp,
        )
