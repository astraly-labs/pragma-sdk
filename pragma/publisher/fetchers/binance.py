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

SUPPORTED_ASSETS = [("BTC", "USDT"), ("ETH", "USDT")]

class BinanceFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.binance.com/api/v3/ticker/24hr"
    SOURCE: str = "BINANCE"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}?symbol={pair[0]}{pair[1]}"
        if pair == ("ETH", "STRK"):
            url = f"{self.BASE_URL}?symbol=STRKUSDT"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Binance"
                    )
                result = await resp.json()
                if 'code' in result:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Binance"
                    )
                eth_url = f"{self.BASE_URL}?symbol=ETHUSDT"
                eth_resp = await session.get(eth_url)
                eth_result = await eth_resp.json()
                return self._construct(asset, result, ((float(eth_result["bidPrice"]) + float(eth_result["askPrice"])))/2)
        else: 
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Binance"
                    )
                result = await resp.json()
                if 'code' in result:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Binance"
                    )
                eth_url = f"{self.BASE_URL}?symbol=ETHUSDT"
                eth_resp = await session.get(eth_url)
                eth_result = await eth_resp.json()
                return self._construct(asset, result)

    def _fetch_pair_sync(
        self, asset: PragmaSpotAsset
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}?symbol={pair[0]}{pair[1]}"
        resp = requests.get(url)
        if resp.status_code == 404:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Binance"
            )
        result = resp.json()
        # if result["code"] == "-1121" or result["msg"] == "Invalid symbol.":
        #     return PublisherFetchError(
        #         f"No data found for {'/'.join(pair)} from Binance"
        #     )
        eth_url = f"{self.BASE_URL}?symbol=ETHUSDT"
        eth_resp = requests.get(eth_url)
        eth_result = eth_resp.json()
        return self._construct(asset, result, (eth_result["bidPrice"] + eth_result["askPrice"])/2)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT":
                entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
            else: 
                logger.debug("Skipping Binance for non-spot asset %s", asset)
                continue
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT" and asset["pair"] in SUPPORTED_ASSETS:
                entries.append(self._fetch_pair_sync(asset))
            else: 
                logger.debug("Skipping Binance for non-spot asset %s", asset)
                continue
        return entries

    def format_url(self, quote_asset, base_asset):
        url = f"{self.BASE_URL}?symbol={quote_asset}{base_asset}"
        return url

    def _construct(self, asset, result, eth_price= None) -> SpotEntry:

        pair = asset["pair"]

        if pair == ("ETH", "STRK"): 
            bid = float(result["bidPrice"])
            ask = float(result["askPrice"])
            strk_price = (bid + ask) / 2
            price = eth_price/strk_price
        else: 
            bid = float(result["bidPrice"])
            ask = float(result["askPrice"])
            price = (bid + ask) / 2
        timestamp = int(time.time())
        price_int = int(price * (10 ** asset["decimals"]))
        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from Binance", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

