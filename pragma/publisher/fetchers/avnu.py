import asyncio
import logging
import time
from typing import Dict, List

import requests
from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

# TODO: Is there a better way ?
ASSET_MAPPING: Dict[str, str] = {
    "ETH": "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
    "USDC": "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
    "USDT": "0x068f5c6a61780768455de69077e07e89787839bf8166decfbf92b645209c0fb8",
    "DAI": "0x00da114221cb83fa859dbdb4c44beeaa0bb37c7537ad5ae66fe5e0efd20e6eb3",
    "WBTC": "0x03fe2b97c1fd336e750087d68b9b867997fd64a2661ff3ca5a7c771641e8e7ac",
    "WSTETH": "0x042b8f0484674ca266ac5d08e4ac6a3fe65bd3129795def2dca5c34ecc5f96d2",
    "LORDS": "0x0124aeb495b947201f5fac96fd1138e326ad86195b98df6dec9009158a533b49",
}


class AvnuFetcher(PublisherInterfaceT):
    BASE_URL: str = "https://starknet.api.avnu.fi/webjars/swagger-ui/index.html#/Swap/getPrices?sellTokenAddress={quote_token}&buyTokenAddress={base_token}&sellAmount={sell_amount}"

    SOURCE: str = "AVNU"
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

        # TODO: Not safe enough
        if pair[1] == "USD":
            pair[1] = "USDC"

        address_0 = ASSET_MAPPING.get(pair[0])
        address_1 = ASSET_MAPPING.get(pair[1])
        if address_0 is None or address_1 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query AVNU for {pair}"
            )

        # Not supported because there is no EUR stablecoin on Starknet
        if pair[1] == "EUR":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")

        decimals = self._fetch_decimals(address_0, sync=False)
        url = self.BASE_URL.format(
            quote_token=address_0,
            base_token=address_1,
            sell_amount=hex(10**decimals),
        )

        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 500:
                return PublisherFetchError(
                    f"Internal Server Error for {'/'.join(pair)} from AVNU"
                )
            result = await resp.json()
            if len(result) == 0:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from AVNU"
                )
            return self._construct(asset, result)

    def _fetch_pair_sync(self, asset: PragmaSpotAsset) -> SpotEntry:
        pair = asset["pair"]

        # TODO: Not safe enough
        if pair[1] == "USD":
            pair[1] = "USDC"

        address_0 = ASSET_MAPPING.get(pair[0])
        address_1 = ASSET_MAPPING.get(pair[1])
        if address_0 is None or address_1 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query AVNU for {pair}"
            )

        # Not supported because there is no EUR stablecoin on Starknet
        if pair[1] == "EUR":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")

        decimals = self._fetch_decimals(address_0, sync=True)
        url = self.BASE_URL.format(
            quote_token=address_0,
            base_token=address_1,
            sell_amount=hex(10**decimals),
        )

        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 500:
            return PublisherFetchError(
                f"Internal Server Error for {'/'.join(pair)} from AVNU"
            )

        result = resp.json()
        if len(result) == 0:
            return PublisherFetchError(f"No data found for {'/'.join(pair)} from AVNU")

        return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug(f"Skipping {self.SOURCE} for non-spot asset {asset}")
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug(f"Skipping {self.SOURCE} for non-spot asset {asset}")
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        address_0 = ASSET_MAPPING.get(quote_asset)
        address_1 = ASSET_MAPPING.get(base_asset)
        if address_0 is None or address_1 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query AVNU for {quote_asset}/{base_asset}"
            )

        decimals = self._fetch_decimals(address_0, sync=False)
        url = self.BASE_URL.format(
            quote_token=address_0, base_token=address_1, sell_amount=hex(10**decimals)
        )
        return url

    # TODO: Aggregate DEXs data based on liquidity/volume data
    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        mid_prices = []
        for dex in result:
            sell_amount_in_usd = float(result["sellAmountInUsd"])
            buy_amount_in_usd = float(result["buyAmountInUsd"])

            # Take the mid price
            mid_price = float((sell_amount_in_usd + buy_amount_in_usd) / 2)
            mid_prices.append(mid_price)

        # Aggregate mid prices
        price = sum(mid_prices) / len(mid_prices)
        price_int = int(price * (10 ** asset["decimals"]))

        timestamp = int(time.time())

        pair_id = currency_pair_to_pair_id(*pair)
        logger.info(f"Fetched price {price} for {pair_id} from AVNU")

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

    async def _fetch_decimals(self, address: str, sync=False) -> int:
        pragma_client = PragmaClient(network="mainnet")

        # Create a call to function "decimals" at address `address`
        call = Call(
            to_addr=address,
            selector=get_selector_from_name("decimals"),
            calldata=[],
        )

        # Pass the created call to Client.call_contract
        if sync:
            [decimals] = pragma_client.client.call_contract_sync(call)
        else:
            [decimals] = await pragma_client.client.call_contract(call)

        return decimals
