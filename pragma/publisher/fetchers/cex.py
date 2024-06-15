import asyncio
import json
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class CexFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://cex.io/api/ticker"
    SOURCE: str = "CEX"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}/{pair[0]}/{pair[1]}"
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from CEX"
                )

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"CEX: Unexpected content type: {content_type}")

            if "error" in result and result["error"] == "Invalid Symbols Pair":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from CEX"
                )

            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping CEX for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}/{quote_asset}/{base_asset}"
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        timestamp = int(result["timestamp"])
        price = float(result["last"])
        price_int = int(price * (10 ** asset["decimals"]))
        volume = float(result["volume"])
        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from CEX", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            volume=int(volume),
            source=self.SOURCE,
            publisher=self.publisher,
        )
