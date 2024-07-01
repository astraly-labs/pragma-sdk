import asyncio
import logging
from typing import List

from aiohttp import ClientSession

from pragma.core.assets import AssetConfig
from pragma.core.entry import SpotEntry
from pragma.core.types import Pair
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class DefillamaFetcher(FetcherInterfaceT):
    BASE_URL: str = (
        "https://coins.llama.fi/prices/current/coingecko:{pair_id}" "?searchWidth=15m"
    )
    SOURCE: str = "DEFILLAMA"

    async def fetch_pair(self, pair: Pair, session: ClientSession) -> SpotEntry:
        pair_id = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[0]}"
            )
        if pair.quote_currency.id != "USD":
            return await self.operate_usd_hop(pair, session)

        url = self.format_url(pair)
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Defillama"
                )
            result = await resp.json()
            if not result["coins"]:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Defillama"
                )
        return self._construct(pair, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for pair in self.pair:
            entries.append(asyncio.ensure_future(self.fetch_pair(pair, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, pair: Pair):
        coingecko_id = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        url = self.BASE_URL.format(pair_id=coingecko_id)
        return url

    async def operate_usd_hop(self, pair: Pair, session) -> SpotEntry:
        coingecko_id_1 = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        coingeck_id_2 = AssetConfig.get_coingecko_id_from_ticker(pair.quote_currency.id)
        if coingeck_id_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[1]} - hop failed"
            )
        url_pair_1 = self.BASE_URL.format(pair_id=coingecko_id_1)
        async with session.get(url_pair_1, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Defillama - hop failed for {pair[0]}"
                )
            result_base = await resp.json()
            if not result_base["coins"]:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Defillama - hop failed for {pair[0]}"
                )
        url_pair_2 = self.BASE_URL.format(pair_id=coingeck_id_2)
        async with session.get(url_pair_2, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Defillama - usd hop failed for {pair[1]}"
                )
            result_quote = await resp.json()
            if not result_quote["coins"]:
                return PublisherFetchError(
                    f"No data found for {pair.id} from Defillama -  usd hop failed for {pair[1]}"
                )
        return self._construct(pair, result_base, result_quote)

    def _construct(self, pair: Pair, result, hop_result=None) -> SpotEntry:
        base_id = AssetConfig.get_coingecko_id_from_ticker(pair.base_currency.id)
        quote_id = AssetConfig.get_coingecko_id_from_ticker(pair.quote_currency.id)
        timestamp = int(result["coins"][f"coingecko:{base_id}"]["timestamp"])
        decimals = pair.decimals()
        if hop_result is not None:
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            hop_price = hop_result["coins"][f"coingecko:{quote_id}"]["price"]
            price_int = int((price / hop_price) * (10**decimals))
        else:
            price = result["coins"][f"coingecko:{base_id}"]["price"]
            price_int = int(price * (10**decimals))

        logger.info("Fetched price %d for %s from Coingecko", price, pair.id)

        entry = SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return entry
