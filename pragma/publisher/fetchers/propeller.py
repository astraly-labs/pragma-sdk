import asyncio
import json
import logging
import time
from typing import Dict, List, Union

import requests
from aiohttp import ClientSession

from pragma.core.assets import PRAGMA_ALL_ASSETS, PragmaAsset, PragmaSpotAsset
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

SELL_AMOUNTS = [1, 10, 100, 1000]

ASSET_MAPPING: Dict[str, str] = {
    "ETH": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USD": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",  # FIXME: Unsafe
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "BTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # FIXME: Unsafe
    "WSTETH": "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0",
    "ZEND": "0xb2606492712d311be8f41d940afe8ce742a52d442",
}

DECIMALS_MAPPING: Dict[str, int] = {
    "ETH": 18,
    "USDC": 6,
    "USD": 6,
    "USDT": 6,
    "DAI": 18,
    "WBTC": 8,
    "BTC": 8,
    "WSTETH": 18,
    "STRK": 18,
    "LUSD": 18,
    "UNI": 18,
    "LORDS": 18,
    "ZEND": 18,
}


class PropellerFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://api.propellerheads.xyz/v2/solver/quote?blockchain=ethereum"
    SOURCE: str = "PROPELLER"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, api_key: str = ""):
        self.assets = assets
        self.publisher = publisher
        self.headers = {"X-Api-Key": api_key}

    # Propeller requires a payload to be sent with the request
    # The payload is a list of orders, each with a sell_token, buy_token, and sell_amount
    # The sell_amount is the amount of the sell_token to be sold
    # The buy_token is the token to be bought
    # The sell_token is the token to be sold
    def build_payload(self, sell_token, buy_token):
        address_0 = ASSET_MAPPING.get(sell_token)
        address_1 = ASSET_MAPPING.get(buy_token)
        sell_amount = 10 ** DECIMALS_MAPPING.get(sell_token) * SELL_AMOUNTS[0]
        if address_0 is None or address_1 is None:
            raise PublisherFetchError(
                f"Unknown price pair, do not know how to query Propeller for {sell_token}/{buy_token}"
            )
        return {
            "orders": [
                {
                    "sell_token": address_0,
                    "buy_token": address_1,
                    "sell_amount": sell_amount,
                }
            ],
        }

    async def _fetch_pair(
        self, asset: PragmaSpotAsset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        pair = asset["pair"]
        url = f"{self.BASE_URL}"
        try:
            payload = self.build_payload(pair[0], pair[1])
        except PublisherFetchError as e:
            return e

        async with session.post(url, headers=self.headers, json=payload) as resp:
            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Propeller"
                )

            if resp.status == 403:
                return PublisherFetchError(
                    "Unauthorized: Please provide an API Key to use PropellerFetcher"
                )

            content_type = resp.content_type
            if content_type and "json" in content_type:
                text = await resp.text()
                result = json.loads(text)
            else:
                raise ValueError(f"PROPELLER: Unexpected content type: {content_type}")

            if "error" in result and result["error"] == "Invalid Symbols Pair":
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Propeller"
                )

            return self._construct(asset, result)

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping Propeller for non-spot asset %s", asset)
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def format_url(self, quote_asset, base_asset):
        url = self.BASE_URL
        return url

    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        mid_prices = []
        for quotes, buy_tokens, sell_tokens in zip(
            result["quotes"], result["buy_tokens"], result["sell_tokens"]
        ):
            sell_amount = float(quotes["sell_amount"])
            buy_amount = float(quotes["buy_amount"])
            sell_decimals = int(sell_tokens["decimals"])
            buy_decimals = int(buy_tokens["decimals"])
            # Take the mid price
            mid_price = (buy_amount / sell_amount) * 10 ** (
                sell_decimals - buy_decimals
            )
            mid_prices.append(mid_price)
        price = sum(mid_prices) / len(mid_prices)
        price_int = int(price * (10 ** asset["decimals"]))

        timestamp = int(time.time())

        pair_id = currency_pair_to_pair_id(*pair)

        logger.info("Fetched price %d for %s from Propeller", price, "/".join(pair))

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            volume=0,
            publisher=self.publisher,
        )
