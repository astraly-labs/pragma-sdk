import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.common.configs import (
    try_get_asset_config_from_ticker,
)
from pragma.common.types.pair import Pair
from pragma.common.types.entry import SpotEntry
from pragma.offchain.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)


class BybitFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.bybit.com/v5/market/tickers?category=spot&"
    SOURCE: str = "BYBIT"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        if pair.quote_currency.id == "USD":
            pair = Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").as_currency(),
            )
        else:
            usdt_price = 1

        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from Bybit")
            result = await resp.json()
            if result["retCode"] == 10001:
                return await self.operate_usdt_hop(pair, session)
            return self._construct(pair=pair, result=result, usdt_price=usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for pair in self.pairs:
            entries.append(
                asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
            )
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}symbol={pair.base_currency.id}{pair.quote_currency.id}"
        return url

    async def operate_usdt_hop(self, pair: Pair, session) -> SpotEntry:
        url_pair1 = self.format_url(
            Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").as_currency(),
            )
        )
        async with session.get(url_pair1) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit - hop failed for {pair[0]}"
                )
            pair1_usdt = await resp.json()
            if pair1_usdt["retCode"] == 10001:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit - hop failed for {pair[0]}"
                )
        url2 = self.format_url(
            Pair(
                pair.quote_currency,
                try_get_asset_config_from_ticker("USDT").as_currency(),
            )
        )
        async with session.get(url2) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit - hop failed for {pair[1]}"
                )
            pair2_usdt = await resp.json()
            if pair2_usdt["retCode"] == 10001:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Bybit - hop failed for {pair[1]}"
                )
        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self, pair: Pair, result, hop_result=None, usdt_price=1
    ) -> SpotEntry:
        bid = float(result["result"]["list"][0]["bid1Price"])
        ask = float(result["result"]["list"][0]["ask1Price"])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result["result"]["list"][0]["bid1Price"])
            hop_ask = float(hop_result["result"]["list"][0]["ask1Price"])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(time.time())
        decimals = pair.decimals()
        price_int = int(price * (10**decimals))
        volume = (
            float(result["result"]["list"][0]["volume24h"]) / 10**decimals
            if hop_result is None
            else 0
        )
        logger.info("Fetched price %d for %s from Bybit", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=volume,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
