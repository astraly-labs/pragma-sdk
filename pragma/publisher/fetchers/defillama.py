import asyncio
import logging
from typing import List

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.types import ASSET_MAPPING
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class DefillamaFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://coins.llama.fi/prices/current/coingecko:{pair_id}" "?searchWidth=15m"
    )

    SOURCE: str = "DEFILLAMA"
    api_key: str

    headers: dict

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, api_key=None):
        self.assets = assets
        self.publisher = publisher
        self.headers = {"Accepts": "application/json"}
        if api_key:
            self.headers["X-Api-Key"] = api_key

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> SpotEntry:
        pair = asset["pair"]
        pair_id = ASSET_MAPPING.get(pair[0])
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[0]}"
            )
        if pair[1] != "USD":
            return await self.operate_usd_hop(asset, session)

        url = self.BASE_URL.format(pair_id=pair_id)
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama"
                )
            result = await resp.json()
            if not result["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama"
                )
        return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping %s for non-spot asset %s", self.SOURCE, asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        pair_id = ASSET_MAPPING.get(quote_asset)
        url = self.BASE_URL.format(pair_id=pair_id)
        return url

    async def operate_usd_hop(self, asset, session) -> SpotEntry:
        pair = asset["pair"]
        pair_id_1 = ASSET_MAPPING.get(pair[0])
        pair_id_2 = ASSET_MAPPING.get(pair[1])
        if pair_id_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[1]} - hop failed"
            )
        url_pair_1 = self.BASE_URL.format(pair_id=pair_id_1)
        async with session.get(url_pair_1, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama - hop failed for {pair[0]}"
                )
            result_base = await resp.json()
            if not result_base["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama - hop failed for {pair[0]}"
                )
        url_pair_2 = self.BASE_URL.format(pair_id=pair_id_2)
        async with session.get(url_pair_2, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama - usd hop failed for {pair[1]}"
                )
            result_quote = await resp.json()
            if not result_quote["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama -  usd hop failed for {pair[1]}"
                )
        return self._construct(asset, result_base, result_quote)

    def _construct(self, asset, result, hop_result=None) -> SpotEntry:
        pair = asset["pair"]
        base_id = ASSET_MAPPING.get(pair[0])
        quote_id = ASSET_MAPPING.get(pair[1])
        pair_id = currency_pair_to_pair_id(*pair)
        timestamp = int(result["coins"][f"coingecko:{base_id}"]["timestamp"])
        if hop_result is not None:
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            hop_price = hop_result["coins"][f"coingecko:{quote_id}"]["price"]
            price_int = int((price / hop_price) * (10 ** asset["decimals"]))
        else:
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            price_int = int(price * (10 ** asset["decimals"]))

        logger.info("Fetched price %d for %s from Coingecko", price, pair_id)

        entry = SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return entry
