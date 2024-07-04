import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.common.fetchers.hop_handler import HopHandler
from pragma.common.types.entry import SpotEntry
from pragma.common.types.pair import Pair
from pragma.common.exceptions import PublisherFetchError
from pragma.common.fetchers.interface import FetcherInterfaceT


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SUPPORTED_ASSETS = [
    ("ETH", "STRK"),
    ("STRK", "USD"),
    ("STRK", "USDT"),
    ("LORDS", "USD"),
    ("LUSD", "USD"),
    ("WBTC", "USD"),
    ("ETH", "LORDS"),
    ("ZEND", "USD"),
    ("ZEND", "USDC"),
    ("ZEND", "USDT"),
    ("ETH", "ZEND"),
    ("NSTR", "USD"),
    ("NSTR", "USDC"),
    ("NSTR", "USDT"),
    ("ETH", "NSTR"),
]


class StarknetAMMFetcher(FetcherInterfaceT):
    EKUBO_PUBLIC_API: str = "https://mainnet-api.ekubo.org"
    SOURCE = "STARKNET"

    hop_handler = HopHandler(
        hopped_currencies={
            "USD": "USDC",
        }
    )

    async def off_fetch_ekubo_price(
        self, pair: Pair, session: ClientSession, timestamp=None
    ) -> Union[SpotEntry, PublisherFetchError]:
        url = self.format_url(pair, timestamp)
        async with session.get(url) as resp:
            if resp.status == 404:
                return PublisherFetchError(f"No data found for {pair} from Starknet")
            if resp.status == 200:
                result_json = await resp.json()
                return self._construct(pair, float(result_json["price"]))
            return await self.operate_eth_hop(pair, session)

    def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        return self.off_fetch_ekubo_price(pair, session)

    def format_url(self, pair: Pair, timestamp=None):
        new_pair = self.hop_handler.get_hop_pair(pair) or pair
        if timestamp:
            return f"{self.EKUBO_PUBLIC_API}/price/{pair.base_currency.id}/{new_pair}?atTime={timestamp}&period=3600"

        return f"{self.EKUBO_PUBLIC_API}/price/{pair.base_currency.id}/{new_pair}?period=3600"

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for pair in self.pairs:
            if pair.to_tuple() in SUPPORTED_ASSETS:
                entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
            else:
                logger.debug("Skipping StarknetAMM for non supported pair: %s", pair)

        return await asyncio.gather(*entries, return_exceptions=True)

    def _construct(self, pair: Pair, result: float) -> SpotEntry:
        price_int = int(result * (10 ** pair.decimals()))
        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
            volume=0,
        )
