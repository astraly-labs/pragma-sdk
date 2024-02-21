import asyncio
import logging
import time
from typing import List, Union

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class HuobiFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.huobi.pro/market/detail/merged"
    SOURCE: str = "HUOBI"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        if pair == ("STRK", "USD"):
            pair = ("STRK", "USDT")
        if pair == ("ETH", "STRK"):
            url = f"{self.BASE_URL}?symbol=strkusdt"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Huobi"
                    )
                result = await resp.json()
                if result["status"] != "ok":
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Huobi"
                    )
                eth_url = f"{self.BASE_URL}?symbol=ethusdt"
                eth_resp = await session.get(eth_url)
                eth_result = await eth_resp.json()
                return self._construct(
                    asset,
                    result,
                    (
                        (
                            float(eth_result["tick"]["ask"][0])
                            + float(eth_result["tick"]["bid"][0])
                        )
                    )
                    / 2,
                )
        else:
            url = f"{self.BASE_URL}?symbol={pair[0].lower()}{pair[1].lower()}"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Huobi"
                    )
                result = await resp.json()
                if result["status"] != "ok":
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Huobi"
                    )
                return self._construct(asset, result)

    def _fetch_pair_sync(
        self, asset: PragmaSpotAsset
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        if pair == ("STRK", "USD"):
            pair = ("STRK", "USDT")
        if pair == ("ETH", "STRK"):
            url = f"{self.BASE_URL}?symbol=strkusdt"
            resp = requests.get(url)
            if resp.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi"
                )
            result = resp.json()
            if result["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi"
                )
            eth_url = f"{self.BASE_URL}?symbol=ethusdt"
            eth_resp = requests.get(eth_url)
            eth_result = eth_resp.json()
            return self._construct(
                asset,
                result,
                (
                    (
                        float(eth_result["tick"]["ask"][0])
                        + float(eth_result["tick"]["bid"][0])
                    )
                )
                / 2,
            )
        else:
            url = f"{self.BASE_URL}?symbol={pair[0].lower()}{pair[1].lower()}"
            resp = requests.get(url)
            if resp.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi"
                )
            result = resp.json()
            if result["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Huobi"
                )
            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT":
                entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
            else:
                logger.debug("Skipping Huobi for non-spot asset %s", asset)
                continue
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT":
                entries.append(self._fetch_pair_sync(asset))
            else:
                logger.debug("Skipping Huobi for non-spot asset %s", asset)
                continue
        return entries

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?symbol={quote_asset}/{base_asset}"
        return url

    def _construct(self, asset, result, eth_price=None) -> SpotEntry:
        pair = asset["pair"]
        data = result["tick"]

        if pair == ("ETH", "STRK"):
            ask = float(data["ask"][0])
            bid = float(data["bid"][0])
            price = (ask + bid) / 2.0
            price_int = int((eth_price / price) * (10 ** asset["decimals"]))
        else:
            ask = float(data["ask"][0])
            bid = float(data["bid"][0])
            price = (ask + bid) / 2.0
            price_int = int(price * (10 ** asset["decimals"]))

        timestamp = int(result["ts"] / 1000)
        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(data["vol"])

        logger.info("Fetched price %d for %s from Huobi", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
