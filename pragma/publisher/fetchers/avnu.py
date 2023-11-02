import asyncio
import logging
import time
from typing import Dict, List

import requests
from aiohttp import ClientSession
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import Call

from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.types import MAINNET, TESTNET, Network
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)

# TODO (#000): Is there a better way ?
ASSET_MAPPING: Dict[Network, Dict[str, str]] = {
    MAINNET: {
        "ETH": "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
        "USDC": "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8",
        "USD": "0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8",  # FIXME: Unsafe
        "USDT": "0x068f5c6a61780768455de69077e07e89787839bf8166decfbf92b645209c0fb8",
        "DAI": "0x00da114221cb83fa859dbdb4c44beeaa0bb37c7537ad5ae66fe5e0efd20e6eb3",
        "WBTC": "0x03fe2b97c1fd336e750087d68b9b867997fd64a2661ff3ca5a7c771641e8e7ac",
        "BTC": "0x03fe2b97c1fd336e750087d68b9b867997fd64a2661ff3ca5a7c771641e8e7ac",  # FIXME: Unsafe
        "WSTETH": "0x042b8f0484674ca266ac5d08e4ac6a3fe65bd3129795def2dca5c34ecc5f96d2",
        "LORDS": "0x0124aeb495b947201f5fac96fd1138e326ad86195b98df6dec9009158a533b49",
    },
    TESTNET: {
        "ETH": "0x049d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7",
        "USDC": "0x005a643907b9a4bc6a55e9069c4fd5fd1f5c79a22470690f75556c4736e34426",
        "USD": "0x005a643907b9a4bc6a55e9069c4fd5fd1f5c79a22470690f75556c4736e34426",
        "USDT": "0x0386e8d061177f19b3b485c20e31137e6f6bc497cc635ccdfcab96fadf5add6a",
        "DAI": "0x03e85bfbb8e2a42b7bead9e88e9a1b19dbccf661471061807292120462396ec9",
        "WBTC": "0x012d537dc323c439dc65c976fad242d5610d27cfb5f31689a0a319b8be7f3d56",
        "BTC": "0x012d537dc323c439dc65c976fad242d5610d27cfb5f31689a0a319b8be7f3d56",
        "WSTETH": "0x0335bc6e1cf6d9527da4f8044c505906ad6728aeeddfba8d7000b01b32ffe66b",
        "LORDS": "0x0",
    },
}


def get_asset_address(asset: str, network: Network):
    return ASSET_MAPPING.get(network, TESTNET).get(asset)


class AvnuFetcher(PublisherInterfaceT):
    BASE_URL: str = (
        "https://{network}.api.avnu.fi/swap/v1/prices?"
        "sellTokenAddress={quote_token}"
        "&buyTokenAddress={base_token}"
        "&sellAmount={sell_amount}"
    )

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

        url = await self.format_url_async(pair[0], pair[1])

        async with session.get(url, headers=self.headers) as resp:
            if resp.status == 500:
                return PublisherFetchError(
                    f"Internal Server Error for {'/'.join(pair)} from AVNU"
                )

            if resp.status == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from AVNU"
                )

            result = await resp.json()
            if len(result) == 0:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from AVNU"
                )
            return self._construct(asset, result)

    def _fetch_pair_sync(self, asset: PragmaSpotAsset) -> SpotEntry:
        pair = asset["pair"]

        address_0 = get_asset_address(pair[0], self.network)
        address_1 = get_asset_address(pair[1], self.network)
        if address_0 is None or address_1 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query AVNU for {pair}"
            )

        # Not supported because there is no EUR stablecoin on Starknet
        if pair[1] == "EUR":
            return PublisherFetchError(f"Base asset not supported : {pair[1]}")

        decimals = self._fetch_decimals_sync(address_0)
        url = self.BASE_URL.format(
            network={
                "mainnet": "starknet",
                "testnet": "goerli",
            }[self.network],
            quote_token=address_0,
            base_token=address_1,
            sell_amount=hex(10**decimals),
        )

        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 500:
            return PublisherFetchError(
                f"Internal Server Error for {'/'.join(pair)} from AVNU"
            )
        if resp.status_code == 404:
            return PublisherFetchError(f"No data found for {'/'.join(pair)} from AVNU")

        result = resp.json()
        if len(result) == 0:
            return PublisherFetchError(f"No data found for {'/'.join(pair)} from AVNU")

        return self._construct(asset, result)

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping {self.SOURCE} for non-spot asset {asset}")
                continue
            entries.append(asyncio.ensure_future(self._fetch_pair(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT":
                logger.debug("Skipping {self.SOURCE} for non-spot asset {asset}")
                continue
            entries.append(self._fetch_pair_sync(asset))
        return entries

    def format_url(self, quote_asset, base_asset):
        address_0 = get_asset_address(quote_asset, self.network)
        address_1 = get_asset_address(base_asset, self.network)
        if address_0 is None or address_1 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query AVNU for {quote_asset}/{base_asset}"
            )

        decimals = self._fetch_decimals_sync(address_0)

        url = self.BASE_URL.format(
            network={
                "mainnet": "starknet",
                "testnet": "goerli",
            }[self.network],
            quote_token=address_0,
            base_token=address_1,
            sell_amount=hex(10**decimals),
        )
        return url

    async def format_url_async(self, quote_asset, base_asset):
        address_0 = get_asset_address(quote_asset, self.network)
        address_1 = get_asset_address(base_asset, self.network)
        if address_0 is None or address_1 is None:
            return PublisherFetchError(
                f"Unknown price pair, do not know how to query AVNU for {quote_asset}/{base_asset}"
            )

        decimals = await self._fetch_decimals(address_0)
        url = self.BASE_URL.format(
            network={
                "mainnet": "starknet",
                "testnet": "goerli",
            }[self.network],
            quote_token=address_0,
            base_token=address_1,
            sell_amount=hex(10**decimals),
        )
        return url

    # TODO (#000): Aggregate DEXs data based on liquidity/volume data
    def _construct(self, asset, result) -> SpotEntry:
        pair = asset["pair"]

        mid_prices = []
        for dex in result:
            sell_amount_in_usd = float(dex["sellAmountInUsd"])
            # buy_amount_in_usd = float(dex["buyAmountInUsd"])

            # Take the mid price
            # mid_price = float((sell_amount_in_usd + buy_amount_in_usd) / 2)
            mid_prices.append(sell_amount_in_usd)

        # Aggregate mid prices
        price = sum(mid_prices) / len(mid_prices)
        price_int = int(price * (10 ** asset["decimals"]))

        timestamp = int(time.time())

        pair_id = currency_pair_to_pair_id(*pair)
        logger.info("Fetched price %d for %s from AVNU", price, pair_id)

        return SpotEntry(
            pair_id=pair_id,
            price=price_int,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

    # pylint: disable=no-self-use
    def _pragma_client(self):
        return PragmaClient(network="mainnet")

    @property
    def network(self) -> Network:
        return self._pragma_client().network

    async def _fetch_decimals(self, address: str) -> int:
        # Create a call to function "decimals" at address `address`
        call = Call(
            to_addr=int(address, 16),
            selector=get_selector_from_name("decimals"),
            calldata=[],
        )

        # Pass the created call to Client.call_contract
        [decimals] = await self._pragma_client().client.call_contract(call)
        return decimals

    def _fetch_decimals_sync(self, address: str) -> int:
        # Create a call to function "decimals" at address `address`
        call = Call(
            to_addr=int(address, 16),
            selector=get_selector_from_name("decimals"),
            calldata=[],
        )

        # Pass the created call to Client.call_contract
        [decimals] = self._pragma_client().client.call_contract_sync(call)

        return decimals
