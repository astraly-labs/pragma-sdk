import asyncio
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class BitstampFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://www.bitstamp.net/api/v2/ticker"
    SOURCE: str = "BITSTAMP"
    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}/{pair[0].lower()}{pair[1].lower()}"
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bitstamp"
                )
            return self._construct(asset, await resp.json())

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []

        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Bitstamp for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}/{quote_asset.lower()}{base_asset.lower()}"
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        timestamp = int(result["timestamp"])
        price = float(result["last"])
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from Bitstamp", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
