import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class AscendexFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://ascendex.com/api/pro/v1/spot/ticker"
    SOURCE: str = "ASCENDEX"
    client: PragmaClient
    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, client=None):
        self.assets = assets
        self.publisher = publisher
        self.client = client or PragmaClient(network="mainnet")

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        if pair[1] == "USD":
            pair = (pair[0], "USDT")
        else:
            usdt_price = 1
        url = self.format_url(pair[0], pair[1])
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Ascendex"
                )
            result = await resp.json()
            if result["code"] == 100002 and result["reason"] == "DATA_NOT_AVAILABLE":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Ascendex"
                )

            return self._construct(asset, result, usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        # Fetching usdt price (done one time)
        usdt_price = await self.get_stable_price("USDT")
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Ascendex for non-spot asset %s", asset)
                continue
            entries.append(
                asyncio.ensure_future(self.fetch_pair(asset, session, usdt_price))
            )
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?symbol={quote_asset}/{base_asset}"
        return url

    def _construct(self, asset, result, usdt_price) -> SpotEntry:
        pair = asset["pair"]
        data = result["data"]
        timestamp = int(time.time())
        ask = float(data["ask"][0])
        bid = float(data["bid"][0])
        price = (ask + bid) / (2.0 * usdt_price)
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(data["volume"])

        logger.info("Fetched price %d for %s from Ascendex", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=int(volume),
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
