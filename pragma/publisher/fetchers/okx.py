import asyncio
import json
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class OkxFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://okx.com/api/v5/market/ticker"
    SOURCE: str = "OKX"
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
        url = f"{self.BASE_URL}?instId={pair[0]}-{pair[1]}-SWAP"
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from OKX"
                )

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"OKX: Unexpected content type: {content_type}")

            if (
                result["code"] == "51001"
                or result["msg"] == "Instrument ID does not exist"
            ):
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from OKX"
                )

            return self._construct(asset, result, usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping OKX for non-spot asset %s", asset)
                continue
            entries.append(
                asyncio.ensure_future(self.fetch_pair(asset, session, usdt_price))
            )
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?instId={quote_asset}-{base_asset}-SWAP"
        return url

    def _construct(self, asset, result, usdt_price=1) -> SpotEntry:
        pair = asset["pair"]
        data = result["data"][0]

        timestamp = int(int(data["ts"]) / 1000)
        price = float(data["last"]) / usdt_price
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(data["volCcy24h"])

        logger.info("Fetched price %d for %s from OKX", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
