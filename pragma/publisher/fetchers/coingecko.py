import asyncio
import datetime
import logging
from typing import Dict, List

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
    "MKR": "maker",
    "BAL": "balancer",
}


class CoingeckoFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://api.coingecko.com/api/v3/coins/{pair_id}"
        "?localization=false&market_data=true&community_data=false"
        "&developer_data=false&sparkline=false"
    )

    SOURCE: str = "COINGECKO"
    headers = {
        "Accepts": "application/json",
    }

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    async def fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> SpotEntry:
        pair = asset["pair"]
        url = self.format_url(ASSET_MAPPING.get(pair[0]), None)
        async with session.get(
            url, headers=self.headers, raise_for_status=True
        ) as resp:
            result = await resp.json()
            return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping %s for non-spot asset %s", self.SOURCE, asset)
                continue
            entries.append(asyncio.ensure_future(self.fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, _) -> str:
        pair_id = ASSET_MAPPING.get(quote_asset)
        if pair_id is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query Coingecko for {quote_asset}"
            )
        url = self.BASE_URL.format(pair_id=pair_id)
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]
        pair_id = currency_pair_to_pair_id(*pair)
        price = result["market_data"]["current_price"][pair[1].lower()]
        price_int = int(price * (10 ** asset["decimals"]))
        timestamp = int(
            datetime.datetime.strptime(
                result["last_updated"],
                "%Y-%m-%dT%H:%M:%S.%f%z",
            ).timestamp()
        )

        logger.info("Fetched price %d for %s from Coingecko", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )
