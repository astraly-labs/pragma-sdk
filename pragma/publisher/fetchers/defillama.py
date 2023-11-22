import asyncio
import logging
from typing import Dict, List

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

ASSET_MAPPING: Dict[str, str] = {
    "ETH": "ethereum",
    "BTC": "bitcoin",
    "WBTC": "wrapped-bitcoin",
    "SOL": "solana",
    "AVAX": "avalanche-2",
    "DOGE": "dogecoin",
    "SHIB": "shiba-inu",
    "TEMP": "tempus",
    "DAI": "dai",
    "USDT": "tether",
    "USDC": "usd-coin",
    "TUSD": "true-usd",
    "BUSD": "binance-usd",
    "BNB": "binancecoin",
    "ADA": "cardano",
    "XRP": "ripple",
    "MATIC": "matic-network",
    "AAVE": "aave",
    "R": "r",
    "LORDS": "lords",
    "WSTETH": "wrapped-steth",
    "UNI": "uniswap",
    "LUSD": "liquity-usd",
}


class DefillamaFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://coins.llama.fi/prices/current/coingecko:{pair_id}" "?searchWidth=5m"
    )

    SOURCE: str = "DEFILLAMA"
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
        pair_id = ASSET_MAPPING.get(pair[0])
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[0]}"
            )
        if pair[1] != "USD":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")
        url = self.BASE_URL.format(pair_id=pair_id)

        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama"
                )
            result = await resp.json()
            if not result["coins"]:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Defillama"
                )
            return self._construct(asset, result)

    def _fetch_pair_sync(self, asset: PragmaSpotAsset) -> SpotEntry:
        pair = asset["pair"]
        pair_id = ASSET_MAPPING.get(pair[0])
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {pair[0]}"
            )
        if pair[1] != "USD":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")
        url = self.BASE_URL.format(pair_id=pair_id)

        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 404:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama"
            )
        result = resp.json()
        if not result["coins"]:
            return PublisherFetchError(
                f"No data found for {'/'.join(pair)} from Defillama"
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

    def fetch_sync(self) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping %s for non-spot asset %s", self.SOURCE, asset)
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        pair_id = ASSET_MAPPING.get(quote_asset)
        url = self.BASE_URL.format(pair_id=pair_id)
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]
        cg_id = ASSET_MAPPING.get(pair[0])
        pair_id = currency_pair_to_pair_id(*pair)
        price = result["coins"][f"coingecko:{cg_id}"]["price"]
        price_int = int(price * (10 ** asset["decimals"]))
        timestamp = int(result["coins"][f"coingecko:{cg_id}"]["timestamp"])

        logger.info("Fetched price %d for %s from Coingecko", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
