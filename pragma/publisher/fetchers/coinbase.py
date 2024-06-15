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


class CoinbaseFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.coinbase.com/v2/exchange-rates?currency="
    SOURCE: str = "COINBASE"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        currency = pair[1]

        async with session.get(self.BASE_URL + currency) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Coinbase"
                )
            result = await resp.json()
            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Coinbase for non-spot asset %s", asset)
                continue

            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = self.BASE_URL + base_asset
        return url

    def _construct(self, asset, result) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        pair_id = currency_pair_to_pair_id(*pair)

        if pair[0] in result["data"]["rates"]:
            rate = float(result["data"]["rates"][pair[0]])
            price = 1 / rate
            price_int = int(price * (10 ** asset["decimals"]))
            timestamp = int(time.time())

            logger.info("Fetched price %d for %s from Coinbase", price, pair_id)

            return SpotEntry(
                pair_id=pair_id,
                price=price_int,
                timestamp=timestamp,
                source=self.SOURCE,
                publisher=self.publisher,
            )

        return PublisherFetchError(f"No entry found for {pair_id} from Coinbase")
