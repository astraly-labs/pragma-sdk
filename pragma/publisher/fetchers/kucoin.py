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


class KucoinFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.kucoin.com/api/v1/market/orderbook/level1"
    SOURCE: str = "KUCOIN"

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
            url = f"{self.BASE_URL}?symbol=STRK-USDT"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Kucoin"
                    )
                result = await resp.json()
                if result["data"] == None:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Kucoin"
                    )

                eth_url = f"{self.BASE_URL}?symbol=ETH-USDT"
                eth_resp = await session.get(eth_url)
                eth_result = await eth_resp.json()
                return self._construct(
                    asset,
                    result,
                    (
                        (
                            float(eth_result["data"]["bestAsk"])
                            + float(eth_result["data"]["bestBid"])
                        )
                        / 2
                    ),
                )
        else:
            url = f"{self.BASE_URL}?symbol={pair[0]}-{pair[1]}"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Kucoin"
                    )
                result = await resp.json()
                if result["data"] == None:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Kucoin"
                    )

                return self._construct(asset, result)

    def _fetch_pair_sync(
        self, asset: PragmaSpotAsset
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        if pair == ("STRK", "USD"):
            pair = ("STRK", "USDT")
        if pair == ("ETH", "STRK"):
            url = f"{self.BASE_URL}?symbol=STRK-USDT"
            resp = requests.get(url)
            if resp.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Kucoin"
                )
            result = resp.json()
            if result["data"] == None:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Kucoin"
                )

            eth_url = f"{self.BASE_URL}?symbol=ETH-USDT"
            eth_resp = requests.get(eth_url)
            eth_result = eth_resp.json()
            return self._construct(
                asset,
                result,
                (
                    (
                        float(eth_result["data"]["bestAsk"])
                        + float(eth_result["data"]["bestBid"])
                    )
                    / 2
                ),
            )
        else:
            url = f"{self.BASE_URL}?symbol={pair[0]}-{pair[1]}"
            resp = requests.get(url)
            if resp.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Kucoin"
                )
            result = resp.json()
            if result["data"] == None:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Kucoin"
                )

            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Kucoin for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Kucoin for non-spot asset %s", asset)
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?symbol={quote_asset}/{base_asset}"
        return url

    def _construct(self, asset, result, eth_price=None) -> SpotEntry:
        pair = asset["pair"]
        data = result["data"]

        if pair == ("ETH", "STRK"):
            price = eth_price / float(data["price"])
            price_int = int(price * (10 ** asset["decimals"]))
            timestamp = int(data["time"] / 1000)
        else:
            price = float(data["price"])
            price_int = int(price * (10 ** asset["decimals"]))

        timestamp = int(data["time"] / 1000)
        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from Kucoin", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
