import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class GeminiFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.gemini.com/v1"
    SOURCE: str = "GEMINI"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = self.BASE_URL + "/pricefeed"

        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from CEX"
                )
            result_json = await resp.json()
            result = [e for e in result_json if e["pair"] == "".join(pair)]

            if len(result) == 0:
                return PublisherFetchError(
                    f"No entry found for {'/'.join(pair)} from Gemini"
                )

            if len(result) > 1:
                return PublisherFetchError(
                    f"Found more than one matching entries for Gemini response and price pair {pair}"
                )

            return self._construct(asset, result[0])

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Gemini for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = self.BASE_URL + "/pricefeed"
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        timestamp = int(time.time())
        price = float(result["price"])
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from CEX", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
