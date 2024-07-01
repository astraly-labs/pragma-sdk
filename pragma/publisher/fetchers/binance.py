import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import try_get_asset_config_from_ticker
from pragma.core.types import Pair
from pragma.core.entry import SpotEntry
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


EXCEPTION_LIST = [...]  # TODO: add exception list


class BinanceFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.binance.com/api/v3/ticker/24hr"
    SOURCE: str = "BINANCE"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        # TODO: remove that
        if pair[1] == "USD":
            pair = Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").get_currency(),
            )
        if pair[0] == "WETH":
            pair = Pair(
                try_get_asset_config_from_ticker("ETH").get_currency(),
                pair.quote_currency,
            )
        else:
            usdt_price = 1

        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from Binance")

            result = await resp.json()
            if "code" in result:
                return await self.operate_usdt_hop(pair, session)
            return self._construct(pair=pair, result=result, usdt_price=usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        usdt_price = await self.get_stable_price("USDT")
        for pair in self.pairs:
            if pair not in EXCEPTION_LIST:
                entries.append(
                    asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
                )

        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}?symbol={pair.base_currency.id}{pair.quote_currency.id}"
        return url

    async def operate_usdt_hop(self, pair: Pair, session) -> SpotEntry:
        url_pair1 = self.format_url(
            Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").get_currency(),
            )
        )
        async with session.get(url_pair1) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance - hop failed for {pair[0]}"
                )
            pair1_usdt = await resp.json()
            if "code" in pair1_usdt:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance - hop failed for {pair[0]}"
                )

        url_pair2 = self.format_url(
            Pair(
                pair.quote_currency,
                try_get_asset_config_from_ticker("USDT").get_currency(),
            )
        )
        async with session.get(url_pair2) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance - hop failed for {pair[1]}"
                )
            pair2_usdt = await resp.json()
            if "code" in pair2_usdt:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Binance - hop failed for {pair[1]}"
                )

        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self, pair: Pair, result, hop_result=None, usdt_price=1
    ) -> SpotEntry:
        bid = float(result["bidPrice"])
        ask = float(result["askPrice"])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result["bidPrice"])
            hop_ask = float(hop_result["askPrice"])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(time.time())
        price_int = int(price * (10 ** pair.decimals()))

        logger.info("Fetched price %d for %s from Binance", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
