import asyncio
import logging
import time
from typing import List, Union
import json
import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id, str_to_felt
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class IndexCoopFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.indexcoop.com"
    SOURCE: str = "INDEXCOOP"
    client: PragmaClient
    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, client=None):
        self.assets = assets
        self.publisher = publisher
        self.client = client or PragmaClient(network="mainnet")

    async def _fetch_pair(
    self, asset: PragmaSpotAsset, session: ClientSession, usdt_price=1
) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = self.format_url(pair[0])
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Ascendex"
                )
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                response_text = await resp.text()
                parsed_data = json.loads(response_text)
                print(parsed_data)
                logger.warning(f"Unexpected content type received: {content_type}")

            return self._construct(asset, parsed_data, usdt_price)

        

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "INDEX":
                logger.debug("Skipping Ascendex for non-index asset %s", asset)
                continue
            entries.append(
                asyncio.ensure_future(self._fetch_pair(asset, session))
            )
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset= None):
        url = f"{self.BASE_URL}/{quote_asset}/analytics"
        return url

    def _construct(self, asset, result, usdt_price) -> SpotEntry:
        pair = asset["pair"]
        timestamp = int(time.time())
        price = result["navPrice"]
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = result["symbol"]
        volume = int(float(result["volume24h"])* (10 ** asset["decimals"]))

        logger.info("Fetched price %d for %s from IndexCoop", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            autoscale_volume=False,
        )


import asyncio 

from pragma.core.assets import PRAGMA_ALL_ASSETS

async def main(): 
    fetcher = IndexCoopFetcher(PRAGMA_ALL_ASSETS, "IndexCoop")
    async with ClientSession() as session:
        result = await fetcher.fetch(session)
        print(result)

asyncio.run(main())
