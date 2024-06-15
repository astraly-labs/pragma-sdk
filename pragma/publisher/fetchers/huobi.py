import asyncio
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class HuobiFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.huobi.pro/market/detail/merged"
    SOURCE: str = "HUOBI"
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
                    f"No data found for {'/'.join(pair)} from Huobi"
                )
            result = await resp.json()
            if result["status"] != "ok":
                return await self.operate_usdt_hop(asset, session)
            return self._construct(asset=asset, result=result, usdt_price=usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for asset in self.assets:
            if asset["type"] == "SPOT":
                entries.append(
                    asyncio.ensure_future(self.fetch_pair(asset, session, usdt_price))
                )
            else:
                logger.debug("Skipping Huobi for non-spot asset %s", asset)
                continue
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?symbol={quote_asset.lower()}{base_asset.lower()}"
        return url

    async def operate_usdt_hop(self, asset, session) -> SpotEntry:
        pair = asset["pair"]
        url_pair1 = self.format_url(asset["pair"][0], "USDT")
        async with session.get(url_pair1) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi - hop failed for {pair[0]}"
                )
            pair1_usdt = await resp.json()
            if pair1_usdt["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi - hop failed for {pair[0]}"
                )
        url_pair2 = self.format_url(asset["pair"][1], "USDT")
        async with session.get(url_pair2) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi - hop failed for {pair[1]}"
                )
            pair2_usdt = await resp.json()
            if pair2_usdt["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi - hop failed for {pair[1]}"
                )
        return self._construct(asset=asset, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(self, asset, result, hop_result=None, usdt_price=1) -> SpotEntry:
        pair = asset["pair"]
        bid = float(result["tick"]["bid"][0])
        ask = float(result["tick"]["ask"][0])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result["tick"]["bid"][0])
            hop_ask = float(hop_result["tick"]["ask"][0])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(result["ts"] / 1000)
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(result["tick"]["vol"]) if hop_result is None else 0
        logger.info("Fetched price %d for %s from Bybit", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=int(volume),
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
