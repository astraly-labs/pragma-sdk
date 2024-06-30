import asyncio
import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import try_get_asset_config_from_ticker
from pragma.core.types import Pair
from pragma.publisher.client import PragmaOnChainClient
from pragma.core.entry import SpotEntry
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class MEXCFetcher(FetcherInterfaceT):
    BASE_URL: str = "https://api.mexc.com/api/v3/ticker/24hr"
    client: PragmaOnChainClient
    SOURCE: str = "MEXC"
    publisher: str

    def __init__(self, pairs: List[Pair], publisher, client=None):
        self.pairs = pairs
        self.publisher = publisher
        self.client = client or PragmaOnChainClient(network="mainnet")

    async def fetch_pair(
        self, pair: Pair, session: ClientSession, usdt_price=1
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = pair["pair"]

        # For now still leaving this line,
        if pair.quote_currency.id == "USD":
            pair = Pair(
                pair.base_currency,
                try_get_asset_config_from_ticker("USDT").get_currency(),
            )
        if pair.base_currency.id == "WETH":
            pair = Pair(
                try_get_asset_config_from_ticker("ETH").get_currency(),
                pair.quote_currency,
            )
        else:
            usdt_price = 1

        url = self.format_url(pair)
        async with session.get(url) as resp:
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from MEXC"
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
            if pair["type"] == "SPOT":
                entries.append(
                    asyncio.ensure_future(self.fetch_pair(pair, session, usdt_price))
                )
            else:
                logger.debug("Skipping MEXC for non-spot pair %s", pair)
                continue
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
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from MEXC - hop failed for {pair.base_currency.id}"
                )
            pair1_usdt = await resp.json()
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from MEXC - hop failed for {pair.base_currency.id}"
                )
        url_pair2 = self.format_url(pair["pair"][1], "USDT")
        async with session.get(url_pair2) as resp:
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from MEXC - hop failed for {pair[1]}"
                )
            pair2_usdt = await resp.json()
            if resp.status == 400:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from MEXC - hop failed for {pair[1]}"
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
        price_int = int(price * (10 ** pair["decimals"]))
        volume = int(float(result["quoteVolume"])) if hop_result is None else 0

        logger.info("Fetched price %d for %s from MEXC", price, pair.id)

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=volume,
        )
