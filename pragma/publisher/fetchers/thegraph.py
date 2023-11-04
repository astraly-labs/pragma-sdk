import asyncio
import logging
import time
from typing import Dict, List

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

ASSET_MAPPING: Dict[str, str] = {
    "ETH": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",  # WETH/USDC 500bps pool
    "BTC": "0x99ac8ca7087fa4a2a1fb6357269965a2014abc35",  # WBTC/USDC 30bps pool
    "WBTC": "0x99ac8ca7087fa4a2a1fb6357269965a2014abc35",  # WBTC/USDC 30bps pool
    "DAI": "0x5777d92f208679db4b9778590fa3cab3ac9e2168",  # DAI/USDC 100bps pool
    "USDC": "0x3416cf6c708da44db2624d63ea0aaef7113527c6",  # USDC/USDT 100bps pool
}


class TheGraphFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.thegraph.com/subgraphs/name/"
    SOURCE: str = "THEGRAPH"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> SpotEntry:
        pair = asset["pair"]
        pool = ASSET_MAPPING.get(pair[0])
        if pool is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query TheGraph for {pair[0]}"
            )
        if pair[1] != "USD":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")

        url_slug = "uniswap/uniswap-v3"
        query = (
            f"query "
            f'{{pool(where: {{id: "{pool}"}}) '
            f"{{volumeUSD token0Price token1Price liquidity sqrtPrice feeTier tick token0 {{symbol}} token1 {{symbol}}}}}}"
        )

        async with session.post(
            self.BASE_URL + url_slug, json={"query": query}
        ) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from TheGraph"
                )
            result_json = await resp.json()
            result = result_json["data"]["pool"]

            return self._construct(asset, result)

    def _fetch_pair_sync(self, asset: PragmaSpotAsset) -> SpotEntry:
        pair = asset["pair"]
        pool = ASSET_MAPPING.get(pair[0])
        if pool is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query TheGraph for {pair[0]}"
            )
        if pair[1] != "USD":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")

        url_slug = "uniswap/uniswap-v3"
        query = (
            f"query "
            f'{{pool(where: {{id: "{pool}"}}) '
            f"{{volumeUSD token0Price token1Price liquidity sqrtPrice feeTier tick token0 {{symbol}} token1 {{symbol}}}}}}"
        )

        resp = requests.post(self.BASE_URL + url_slug, json={"query": query})
        if resp.status_code == 404:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from TheGraph"
            )
        result_json = resp.json()
        result = result_json["data"]["pool"]
        return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping The Graph for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping The Graph for non-spot asset %s", asset)
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        pool = ASSET_MAPPING[quote_asset]
        url_slug = "uniswap/uniswap-v3"
        url = self.BASE_URL + url_slug
        return url

    def query_body(self, quote_asset):
        pool = ASSET_MAPPING[quote_asset]
        query = (
            f"query "
            f'{{pool(where: {{id: "{pool}"}}) '
            f"{{volumeUSD token0Price token1Price liquidity sqrtPrice feeTier tick token0 {{symbol}} token1 {{symbol}}}}}}"
        )
        return query

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        if pair[0] in result["token0"]["symbol"]:
            price = float(result["token1Price"])
        else:
            price = float(result["token0Price"])

        price_int = int(price * (10 ** asset["decimals"]))
        volume = float(result["volumeUSD"])

        timestamp = int(time.time())

        pair_id = currency_pair_to_pair_id(*pair)
        logger.info("Fetched data %s for %s from The Graph", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=volume,
        )
