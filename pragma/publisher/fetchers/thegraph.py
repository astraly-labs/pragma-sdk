import asyncio
import logging
import time
from typing import Dict, List

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id, str_to_felt
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

ASSET_MAPPING: Dict[str, str] = {
    "ETH": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",  # WETH/USDC 500bps pool
    "BTC": "0x99ac8ca7087fa4a2a1fb6357269965a2014abc35",  # WBTC/USDC 30bps pool
    "WBTC": "0x99ac8ca7087fa4a2a1fb6357269965a2014abc35",  # WBTC/USDC 30bps pool
    "DAI": "0x5777d92f208679db4b9778590fa3cab3ac9e2168",  # DAI/USDC 100bps pool
    "USDC": "0x3416cf6c708da44db2624d63ea0aaef7113527c6",  # USDC/USDT 100bps pool
}


def query_body(quote_asset):
    pool = ASSET_MAPPING[quote_asset]
    query = (
        f'{{pool(id: "{pool}")'
        f"{{ tick token0 {{ symbol }} token1 {{ symbol }} "
        f"feeTier sqrtPrice liquidity token0Price token1Price volumeUSD}}}}"
    )
    return query


class TheGraphFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.thegraph.com/subgraphs/name/"
    SOURCE: str = "THEGRAPH"
    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, client=None):
        self.assets = assets
        self.publisher = publisher
        self.client = client or PragmaClient(network="mainnet")

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> SpotEntry:
        pair = asset["pair"]
        base_pool = ASSET_MAPPING.get(pair[0])
        if base_pool is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query TheGraph for {pair[0]}"
            )
        quote_result = await self.pool_query(session, query_body(pair[0]), pair)
        if pair[1] != "USDC":
            if pair[1] == "USD":
                usdc_str = str_to_felt("USDC/USD")
                usdc_entry = await self.client.get_spot(usdc_str)
                usdc_price = int(usdc_entry.price) / (10 ** int(usdc_entry.decimals))
                return self._construct(asset, quote_result, usd_price=usdc_price)
            if pair[1] in ASSET_MAPPING:
                base_result = await self.pool_query(session, query_body(pair[1]), pair)
                return self._construct(
                    asset=asset, quote_result=quote_result, base_result=base_result
                )
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")
        return self._construct(asset, quote_result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping The Graph for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, base_asset=None, quote_asset=None):
        url_slug = "uniswap/uniswap-v3"
        url = self.BASE_URL + url_slug
        return url

    async def pool_query(self, session: ClientSession, query: str, pair: List[str]):
        async with session.post(self.format_url(), json={"query": query}) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from TheGraph"
                )
            result_json = await resp.json()
            result = result_json["data"]["pool"]
            return result

    def _construct(
        self, asset, quote_result, base_result=None, usd_price=1
    ) -> SpotEntry:
        pair = asset["pair"]

        if pair[0] in quote_result["token0"]["symbol"]:
            price = float(quote_result["token1Price"]) / usd_price
        else:
            price = float(quote_result["token0Price"]) / usd_price

        if base_result is not None:
            if pair[1] in base_result["token0"]["symbol"]:
                base_price = float(base_result["token1Price"])
            else:
                base_price = float(base_result["token0Price"])
            price = price / base_price
        price_int = int(price * (10 ** asset["decimals"]))
        volume = float(quote_result["volumeUSD"]) * (10 ** asset["decimals"])

        timestamp = int(time.time())

        pair_id = currency_pair_to_pair_id(*pair)
        logger.info("Fetched data %s for %s from The Graph", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=int(volume),
            autoscale_volume=False,
        )
