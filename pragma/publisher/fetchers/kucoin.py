import asyncio
import logging
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import try_get_asset_config_from_ticker
from pragma.core.types import Pair
from pragma.publisher.client import PragmaOnChainClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class KucoinFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.kucoin.com/api/v1/market/orderbook/level1"
    SOURCE: str = "KUCOIN"

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        if pair.quote_currency.id == "USD":
            pair = Pair(
                pair.base_currency, try_get_asset_config_from_ticker("USDT")
            ).get_currency()
        else:
            usdt_price = 1

        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair.id} from Kucoin")
            result = await resp.json()
            if result["data"] is None:
                return await self.operate_usdt_hop(pair, session)
            return self._construct(pair=pair, result=result, usdt_price=usdt_price)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for pair in self.pairs:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        url = f"{self.BASE_URL}?symbol={pair.base_currency.id}-{pair.quote_currency.id}"
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
                    f"No data found for {pair.id} from Kucoin - hop failed for {pair.base_currency}"
                )
            pair1_usdt = await resp.json()
            if pair1_usdt["data"] is None:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Kucoin - hop failed for {pair.base_currency}"
                )
        url_pair2 = self.format_url(
            Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").get_currency(),
            )
        )
        async with session.get(url_pair2) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Kucoin - hop failed for {pair.quote_currency}"
                )
            pair2_usdt = await resp.json()
            if pair2_usdt["data"] is None:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Kucoin - hop failed for {pair.quote_currency}"
                )
        return self._construct(pair=pair, result=pair2_usdt, hop_result=pair1_usdt)

    def _construct(
        self, pair: Pair, result, hop_result=None, usdt_price=1
    ) -> SpotEntry:
        price = float(result["data"]["price"]) / usdt_price
        if hop_result is not None:
            hop_price = float(hop_result["data"]["price"])
            price = hop_price / price
        timestamp = int(result["data"]["time"] / 1000)
        price_int = int(price * (10 ** pair.decimals()))
        logger.info("Fetched price %d for %s from Kucoin", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
