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


ASSET_MAPPING: Dict[str, any] = {
    "LORDS": (
        "starknet-alpha",
        "0x124aeb495b947201f5fac96fd1138e326ad86195b98df6dec9009158a533b49",
    ),
    "R": ("eth", "0x183015a9ba6ff60230fdeadc3f43b3d788b13e21"),
    "WBTC": ("eth", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"),
    "BTC": ("eth", "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599"),
    "WSTETH": ("eth", "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"),
    "ETH": ("eth", "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
    "UNI": ("eth", "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"),
    "LUSD": ("eth", "0x5f98805a4e8be255a32880fdec7f6728c6568ba0"),
    "STRK": (
        "starknet-alpha",
        "0x4718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d",
    ),
    "ZEND": (
        "starknet-alpha",
        "0x00585c32b625999e6e5e78645ff8df7a9001cf5cf3eb6b80ccdd16cb64bd3a34",
    ),
}


class GeckoTerminalFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://api.geckoterminal.com/api/v2/networks/{network}/tokens/{token_address}"
    )

    SOURCE: str = "GECKOTERMINAL"
    headers = {
        "Accepts": "application/json",
    }

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> SpotEntry:
        pair = asset["pair"]
        if pair[1] != "USD":
            return await self.operate_usd_hop(asset, session)
        pool = ASSET_MAPPING.get(pair[0])
        if pool is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query GeckoTerminal for {pair[0]}"
            )

        url = self.BASE_URL.format(network=pool[0], token_address=pool[1])
        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GeckoTerminal"
                )
            result = await resp.json()
            if (
                result.get("errors") is not None
                and result["errors"][0]["title"] == "Not Found"
            ):
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GeckoTerminal"
                )

        return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping %s for non-spot asset %s", self.SOURCE, asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        pool = ASSET_MAPPING[quote_asset]
        url = self.BASE_URL.format(network=pool[0], token_address=pool[1])
        return url

    async def operate_usd_hop(self, asset, session) -> SpotEntry:
        pair = asset["pair"]
        pool_1 = ASSET_MAPPING.get(pair[0])
        pool_2 = ASSET_MAPPING.get(pair[1])
        if pool_1 is None or pool_2 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query GeckoTerminal for hop {pair[0]} to {pair[1]}"
            )

        pair1_url = self.BASE_URL.format(network=pool_1[0], token_address=pool_1[1])

        async with session.get(pair1_url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GeckoTerminal"
                )
            result = await resp.json()
            if (
                result.get("errors") is not None
                and result["errors"][0]["title"] == "Not Found"
            ):
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GeckoTerminal"
                )

        pair2_url = self.BASE_URL.format(network=pool_2[0], token_address=pool_2[1])
        async with session.get(pair2_url, headers=self.headers) as resp2:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GeckoTerminal"
                )
            hop_result = await resp2.json()
            if (
                result.get("errors") is not None
                and result["errors"][0]["title"] == "Not Found"
            ):
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from GeckoTerminal"
                )
        return self._construct(asset, hop_result, result)

    def _construct(self, asset, result, hop_result=None) -> SpotEntry:
        pair = asset["pair"]
        data = result["data"]["attributes"]
        price = float(data["price_usd"])
        if hop_result is not None:
            hop_price = float(hop_result["data"]["attributes"]["price_usd"])
            price_int = int(hop_price / price * 10 ** asset["decimals"])
        else:
            price_int = int(price * (10 ** asset["decimals"]))

        volume = float(data["volume_usd"]["h24"]) / 10 ** asset["decimals"]

        timestamp = int(time.time())

        pair_id = currency_pair_to_pair_id(*pair)
        logger.info("Fetched price %d for %s from GeckoTerminal", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
            volume=int(volume),
            autoscale_volume=True,
        )
