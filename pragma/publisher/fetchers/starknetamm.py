import asyncio
import logging
import math
import time
from typing import List, Union

import requests
from aiohttp import ClientSession
from dotenv import load_dotenv
from starknet_py.hash.selector import get_selector_from_name
from starknet_py.net.client_models import Call

from pragma.core.assets import PragmaAsset
from pragma.core.entry import SpotEntry
from pragma.core.types import PoolKey, get_client_from_network
from pragma.core.utils import currency_pair_to_pair_id
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

load_dotenv()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class StarknetAMMFetcher(PublisherInterfaceT):
    client = get_client_from_network("testnet")
    EKUBO_PUBLIC_API: str = "https://goerli-api.ekubo.org"
    EKUBO_CORE_CONTRACT: str = (
        "0x031e8a7ab6a6a556548ac85cbb8b5f56e8905696e9f13e9a858142b8ee0cc221"
    )
    JEDISWAP_ETH_STRK_POOL: str = (
        "0x4e021092841c1b01907f42e7058f97e5a22056e605dce08a22868606ad675e0"
    )
    # Parameters for the pool

    # These are the parameters of the most used pool in Ekubo for the testing pair ETH/USDC
    POOL_FEE = 0.0005  # 0.05%
    TICK_SPACING = 0.001  # 0.1%
    TICK_BASE = 1.000001
    POOL_EXTENSION = 0

    STRK_ADDRESS: str = (
        "0x04718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d"
    )
    ETH_ADDRESS: str = (
        "0x049D36570D4e46f48e99674bd3fcc84644DdD6b96F7C741B1562B82f9e004dC7"
    )
    ETH_DECIMALS: int = 18
    STRK_DECIMALS: int = 18

    SOURCE = "STARKNET"

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher

    def prepare_call(self) -> Call:
        token_0, token_1 = min(self.ETH_ADDRESS, self.STRK_ADDRESS), max(
            self.ETH_ADDRESS, self.STRK_ADDRESS
        )
        fee = math.floor(self.POOL_FEE * 2**128)
        # An TICK_SPACING increaese of a price means the new price is price*(1+TICK_SPACING)
        # We want to know the number of tick for a price increase of TICK_SPACING
        # Since the tick spacing is represented as an exponent of TICK_BASE, we can use the logarithm to find the number of tick
        tick = round(math.log(1 + self.TICK_SPACING) / math.log(self.TICK_BASE))
        pool_key = PoolKey(
            int(token_0, 16),
            int(token_1, 16),
            int(fee),
            int(tick),
            int(self.POOL_EXTENSION),
        )
        call = Call(
            to_addr=self.EKUBO_CORE_CONTRACT,
            selector=get_selector_from_name("get_pool_price"),
            calldata=pool_key.serialize(),
        )
        return call

    # Version1: fetching the price using the Ekubo API
    def off_fetch_ekubo_price_sync(
        self, asset, time=None
    ) -> Union[float, PublisherFetchError]:
        url = self.format_url(asset["pair"][0], asset["pair"][1], time)
        pair = asset["pair"]
        try:
            response = requests.get(url)
            if response.status_code == 404:
                return PublisherFetchError(
                    f"No data found for {'/'.join(pair)} from Starknet"
                )
            if response.status_code == 200:
                return response.json()["price"]
            else:
                return PublisherFetchError(
                    f"Error: Unable to retrieve data, status code {response.status_code}"
                )
        except Exception as e:
            return f"Error: {e}"

    async def off_fetch_ekubo_price(
        self, asset, session: ClientSession, time=None
    ) -> Union[float, PublisherFetchError]:
        url = self.format_url(asset["pair"][0], asset["pair"][1], time)
        pair = asset["pair"]

        try:
            async with session.get(url) as resp:
                if resp.status == 404:
                    return PublisherFetchError(
                        f"No data found for {'/'.join(pair)} from Starknet"
                    )
                if resp.status == 200:
                    result_json = await resp.json()
                    return result_json["price"]
                else:
                    return PublisherFetchError(
                        f"Error: Unable to retrieve data, status code {resp.status_code}"
                    )
        except Exception as e:
            return f"Error: {e}"

    async def on_fetch_ekubo_price(self) -> float:
        call = self.prepare_call()
        pool_info = await self.client.call_contract(call)
        sqrt_ratio = pool_info[0]
        if sqrt_ratio == 0:
            logger.error("Ekubo: Pool is empty")
        return (
            (sqrt_ratio / 2**128) ** 2 * 10 * (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    def on_fetch_ekubo_price_sync(self) -> float:
        call = self.prepare_call()
        pool_info = self.client.call_contract_sync(call)
        sqrt_ratio = pool_info[0]
        if sqrt_ratio == 0:
            logger.error("Ekubo: Pool is empty")
        return (
            (sqrt_ratio / 2**128) ** 2 * 10 * (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    async def on_fetch_jedi_price(self) -> float:
        call = Call(
            to_addr=self.JEDISWAP_ETH_STRK_POOL,
            selector=get_selector_from_name("get_reserves"),
            calldata=[],
        )
        reserves_infos = await self.client.call_contract(call)
        token_0_reserve = reserves_infos[0] + reserves_infos[1] * 2**128
        token_1_reserve = reserves_infos[2] + reserves_infos[3] * 2**128
        if token_0_reserve == 0 or token_1_reserve == 0:
            logger.error("JediSwap: Pool is empty")
        return (
            token_1_reserve
            / token_0_reserve
            * 10 ** (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    def on_fetch_jedi_price_sync(self) -> float:
        call = Call(
            to_addr=self.JEDISWAP_ETH_STRK_POOL,
            selector=get_selector_from_name("get_reserves"),
            calldata=[],
        )
        reserves_infos = self.client.call_contract_sync(call)
        token_0_reserve = reserves_infos[0] + reserves_infos[1] * 2**128
        token_1_reserve = reserves_infos[2] + reserves_infos[3] * 2**128
        if token_0_reserve == 0 or token_1_reserve == 0:
            logger.error("JediSwap: Pool is empty")
        return (
            token_1_reserve
            / token_0_reserve
            * 10 ** (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    async def fetch_strk(
        self, asset, session: ClientSession
    ) -> Union[SpotEntry, PublisherFetchError]:
        # ekubo_price = await self.on_fetch_ekubo_price()
        ekubo_price = (
            await self.off_fetch_ekubo_price(asset, session)
            if isinstance(await self.off_fetch_ekubo_price(asset, session), float)
            else None
        )
        jedi_swap_price = await self.on_fetch_jedi_price()
        if ekubo_price is not None and jedi_swap_price is not None:
            return self._construct(asset, (ekubo_price + jedi_swap_price) / 2)
        elif ekubo_price is not None:
            return self._construct(asset, ekubo_price)
        elif jedi_swap_price is not None:
            return self._construct(asset, jedi_swap_price)
        else:
            logger.error("Both ekubo_price and jedi_swap_price are null")
            return PublisherFetchError("Both prices are unavailable")

    def fetch_strk_sync(self, asset) -> Union[SpotEntry, PublisherFetchError]:
        # ekubo_price =  self.on_fetch_ekubo_price_sync()
        ekubo_price = (
            self.off_fetch_ekubo_price_sync(asset)
            if isinstance(self.off_fetch_ekubo_price_sync(asset), float)
            else None
        )
        jedi_swap_price = self.on_fetch_jedi_price_sync()
        if ekubo_price is not None and jedi_swap_price is not None:
            return self._construct(asset, (ekubo_price + jedi_swap_price) / 2)
        elif ekubo_price is not None:
            return self._construct(asset, ekubo_price)
        elif jedi_swap_price is not None:
            return self._construct(asset, jedi_swap_price)
        else:
            logger.error("Both ekubo_price and jedi_swap_price are null")
            return PublisherFetchError("Both prices are unavailable")

    def format_url(self, quote_asset, base_asset, time=None):
        if time:
            return f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}?atTime={time}&period=3600"
        else:
            return (
                f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}?period=3600"
            )

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT" or asset["pair"] != ("ETH", "STRK"):
                logger.debug(
                    f"Skipping StarknetAMM for non ETH or non STRK pair: {asset}"
                )
                continue
            entries.append(asyncio.ensure_future(self.fetch_strk(asset, session)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT" or asset["pair"] != ("ETH", "STRK"):
                logger.debug(
                    f"Skipping StarknetAMM for non ETH or non STRK pair: {asset}"
                )
                continue
            entries.append(self.fetch_strk_sync(asset))
        return entries

    def _construct(self, asset, result) -> SpotEntry:
        price_int = int(result * (10 ** asset["decimals"]))
        return SpotEntry(
            pair_id=currency_pair_to_pair_id(asset["pair"][0], asset["pair"][1]),
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )


# def main():
#     fetcher = StarknetAMMFetcher(PRAGMA_ALL_ASSETS,"PRAGMA")
#     price = fetcher.fetch_sync()
#     print(price)

# # Run the main function in the asyncio event loop
# main()
