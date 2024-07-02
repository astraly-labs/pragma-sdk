import asyncio
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.common.configs.asset_config import try_get_asset_config_from_ticker
from pragma.common.types.pair import Pair
from pragma.common.types.entry import SpotEntry
from pragma.offchain.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT

logger = logging.getLogger(__name__)


class HuobiFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.huobi.pro/market/detail/merged"
    SOURCE: str = "HUOBI"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        if pair.quote_currency.id == "USD":
            pair = Pair(
                pair.base_currency, try_get_asset_config_from_ticker("USDT")
            ).as_currency()
        else:
            usdt_price = 1
        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from Huobi")
            result = await resp.json()
            if result["status"] != "ok":
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
        url = f"{self.BASE_URL}?symbol={pair.base_currency.id.lower()}{pair.quote_currency.id.lower()}"
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
                    f"No data found for {pair.id} from Huobi - hop failed for {pair.base_currency}"
                )
            pair1_usdt = await resp.json()
            if pair1_usdt["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {pair.id} from Huobi - hop failed for {pair.base_currency}"
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
                    f"No data found for {pair.id} from Huobi - hop failed for {pair.quote_currency}"
                )
            pair2_usdt = await resp.json()
            if pair2_usdt["status"] != "ok":
                return PublisherFetchError(
                    f"No data found for {pair.id} from Huobi - hop failed for {pair.quote_currency}"
                )
        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self, pair: Pair, result, hop_result=None, usdt_price=1
    ) -> SpotEntry:
        bid = float(result["tick"]["bid"][0])
        ask = float(result["tick"]["ask"][0])
        price = (bid + ask) / (2 * usdt_price)
        if hop_result is not None:
            hop_bid = float(hop_result["tick"]["bid"][0])
            hop_ask = float(hop_result["tick"]["ask"][0])
            hop_price = (hop_bid + hop_ask) / 2
            price = hop_price / price
        timestamp = int(result["ts"] / 1000)
        price_int = int(price * (10 ** pair.decimals()))
        volume = float(result["tick"]["vol"]) if hop_result is None else 0
        logger.info("Fetched price %d for %s from Bybit", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=int(volume),
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
