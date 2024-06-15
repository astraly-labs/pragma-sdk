import asyncio
import json
import logging
import time
from typing import List, Union

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.fetchers.index import AssetQuantities
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

SUPPORTED_INDEXES = {
    "DPI": "0x1494CA1F11D487c2bBe4543E90080AeBa4BA3C2b",
    "MVI": "0x72e364F2ABdC788b7E918bc238B21f109Cd634D7",
}


class IndexCoopFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.indexcoop.com"
    SOURCE: str = "INDEXCOOP"
    client: PragmaClient
    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, client=None):
        self.assets = assets
        self.publisher = publisher
        self.client = client or PragmaClient(network="mainnet")

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = self.format_url(pair[0].lower())
        async with session.get(url) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                response_text = await resp.text()
                if not response_text:
                    return PublisherFetchError(
                        f"No index found for {pair[0]} from IndexCoop"
                    )
                parsed_data = json.loads(response_text)
                logger.warning("Unexpected content type received: %s", content_type)

            return self._construct(asset, parsed_data)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping IndexCoop for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset=None):
        url = f"{self.BASE_URL}/{quote_asset}/analytics"
        return url

    def fetch_quantities(self, index_address) -> List[AssetQuantities]:
        url = f"{self.BASE_URL}/components?chainId=1&isPerpToken=false&address={index_address}"
        response = requests.get(url)
        response.raise_for_status()
        json_response = response.json()

        components = json_response["components"]
        quantities = {
            component["symbol"]: float(component["quantity"])
            for component in components
        }

        return [
            AssetQuantities(
                PragmaSpotAsset(pair=(symbol, "USD"), decimals=8, type="SPOT"),
                quantities,
            )
            for symbol, quantities in quantities.items()
        ]

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]
        timestamp = int(time.time())
        price = result["navPrice"]
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)
        volume = int(float(result["volume24h"]) * (10 ** asset["decimals"]))

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
