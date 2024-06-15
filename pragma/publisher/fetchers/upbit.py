import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

SUPPORTED_ASSETS = [("BTC", "ETH")]


class UpbitFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://sg-api.upbit.com/v1/ticker"
    SOURCE: str = "UPBIT"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = self.format_url(pair[0], pair[1])
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Upbit"
                )
            result = await resp.json()
            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT" and asset["pair"] in SUPPORTED_ASSETS:
                entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
            else:
                logger.debug("Skipping Upbit for non-spot asset %s", asset)
                continue
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?markets={quote_asset}-{base_asset}"
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]
        data = result[0]
        timestamp = int(time.time())
        price = float(data["trade_price"])
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(data["trade_volume"])

        logger.info("Fetched price %d for %s from Upbit", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
