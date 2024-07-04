import asyncio
import json
import logging
import time
from typing import List, Union

import requests
from aiohttp import ClientSession

from pragma.common.configs.asset_config import AssetConfig
from pragma.common.types.currency import Currency
from pragma.common.types.pair import Pair
from pragma.common.types.entry import SpotEntry
from pragma.common.fetchers.fetchers.index import AssetQuantities
from pragma.common.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)

SUPPORTED_INDEXES = {
    "DPI": "0x1494CA1F11D487c2bBe4543E90080AeBa4BA3C2b",
    "MVI": "0x72e364F2ABdC788b7E918bc238B21f109Cd634D7",
}


class IndexCoopFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.indexcoop.com"
    SOURCE: str = "INDEXCOOP"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair)
        async with session.get(url) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                response_text = await resp.text()
                if not response_text:
                    return PublisherFetchError(
                        f"No index found for {pair.base_currency} from IndexCoop"
                    )
                parsed_data = json.loads(response_text)
                logger.warning("Unexpected content type received: %s", content_type)

            return self._construct(pair, parsed_data)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}/{pair.base_currency.id}/analytics"
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
                pair=Pair(
                    Currency.from_asset_config(AssetConfig.from_ticker(symbol)),
                    Currency.from_asset_config(AssetConfig.from_ticker("USD")),
                ),
                quantities=quantities,
            )
            for symbol, quantities in quantities.items()
        ]

    def _construct(self, pair: Pair, result) -> SpotEntry:
        timestamp = int(time.time())
        price = result["navPrice"]
        decimals = pair.decimals()
        price_int = int(price * (10**decimals))
        volume = int(float(result["volume24h"]) * (10**decimals))

        logger.info("Fetched price %d for %s from IndexCoop", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
