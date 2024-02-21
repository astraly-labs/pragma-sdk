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


class BybitFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.bybit.com/v5/market/tickers?category=spot&"
    SOURCE: str = "BYBIT"

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
            url = f"{self.BASE_URL}symbol=STRKUSDT"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Bybit"
                    )
                result = await resp.json()
                if result["retCode"] == 10001:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Bybit"
                    )
                eth_url = f"{self.BASE_URL}symbol=ETHUSDT"
                eth_resp = await session.get(eth_url)
                eth_result = await eth_resp.json()
                return self._construct(
                    asset,
                    result,
                    (
                        (
                            float(eth_result["result"]["list"][0]["bid1Price"])
                            + float(eth_result["result"]["list"][0]["ask1Price"])
                        )
                    )
                    / 2,
                )
        else:
            url = f"{self.BASE_URL}symbol={pair[0]}{pair[1]}"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Bybit"
                    )
                result = await resp.json()
                if result["retCode"] == 10001:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Bybit"
                    )

                return self._construct(asset, result)

    def _fetch_pair_sync(
        self, asset: PragmaSpotAsset
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        if pair == ("STRK", "USD"):
            pair = ("STRK", "USDT")
        if pair == ("ETH", "STRK"):
            url = f"{self.BASE_URL}symbol=STRKUSDT"
            resp = requests.get(url)
            if resp.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit"
                )
            result = resp.json()
            if result["retCode"] == 10001:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit"
                )
            eth_url = f"{self.BASE_URL}symbol=ETHUSDT"
            eth_resp = requests.get(eth_url)
            eth_result = eth_resp.json()
            return self._construct(
                asset,
                result,
                (
                    (
                        float(eth_result["result"]["list"][0]["bid1Price"])
                        + float(eth_result["result"]["list"][0]["ask1Price"])
                    )
                )
                / 2,
            )
        else:
            url = f"{self.BASE_URL}symbol={pair[0]}{pair[1]}"

            resp = requests.get(url)
            if resp.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit"
                )
            result = resp.json()
            if result["retCode"] == 10001:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit"
                )

            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Bybit for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Bybit for non-spot asset %s", asset)
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?symbol={quote_asset}/{base_asset}"
        return url

    def _construct(self, asset, result, eth_price=None) -> SpotEntry:
        pair = asset["pair"]
        data = result["result"]["list"]
        timestamp = int(time.time())
        if pair == ("ETH", "STRK"):
            ask = float(data[0]["ask1Price"])
            bid = float(data[0]["bid1Price"])
            price = (ask + bid) / 2.0
            price_int = int((eth_price / price) * (10 ** asset["decimals"]))
        else:
            ask = float(data[0]["ask1Price"])
            bid = float(data[0]["bid1Price"])
            price = (ask + bid) / 2.0
            price_int = int(price * (10 ** asset["decimals"]))

        pair_id = currency_pair_to_pair_id(*pair)
        volume = float(data[0]["volume24h"]) / 10 ** asset["decimals"]
        logger.info("Fetched price %d for %s from Bybit", price, "/".join(pair))
        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
