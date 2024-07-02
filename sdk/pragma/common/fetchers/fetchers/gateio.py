import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.common.configs.asset_config import try_get_asset_config_from_ticker
from pragma.common.types.entry import SpotEntry
from pragma.common.types.pair import Pair
from pragma.offchain.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)


class GateioFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.gateio.ws/api/v4/spot/tickers"
    SOURCE: str = "GATEIO"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = pair["pair"]

        # For now still leaving this line,
        if pair.quote_currency.id == "USD":
            pair = Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").as_currency(),
            )
        if pair.base_currency.id == "WETH":
            pair = Pair(
                try_get_asset_config_from_ticker("ETH").as_currency(),
                pair.quote_currency,
            )
        else:
            usdt_price = 1

        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GATEIO"
                )
            result = await resp.json()
            if resp.status == 400:
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
        url = f"{self.BASE_URL}?currency_pair={pair.base_currency.id}_{pair.quote_currency.id}"
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
                    f"No data found for {'/'.join(pair)} from Gate.io - hop failed for {pair[0]}"
                )
            pair1_usdt = await resp.json()
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Gate.io - hop failed for {pair[0]}"
                )
        url_pair2 = self.format_url(
            Pair(
                pair.quote_currency,
                try_get_asset_config_from_ticker("USDT").as_currency(),
            )
        )
        async with session.get(url_pair2) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Gate.io - hop failed for {pair[1]}"
                )
            pair2_usdt = await resp.json()
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Gate.io - hop failed for {pair[1]}"
                )
        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self, pair: Pair, result, hop_result=None, usdt_price=1
    ) -> SpotEntry:
        bid = float(result[0]["highest_bid"])
        ask = float(result[0]["lowest_ask"])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result[0]["highest_bid"])
            hop_ask = float(hop_result[0]["lowest_ask"])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(time.time())
        volume = int(float(result[0]["quote_volume"])) if hop_result is None else 0
        price_int = int(price * (10 ** pair.decimals()))

        logger.info("Fetched price %d for %s from Gate.io", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=volume,
        )
