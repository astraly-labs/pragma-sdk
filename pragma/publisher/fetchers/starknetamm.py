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

from pragma.core.assets import PRAGMA_ALL_ASSETS, PragmaAsset

# from starknet_py.net.full_node_client import FullNodeClient
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.types import PoolKey, get_client_from_network, get_rpc_url
from pragma.core.utils import currency_pair_to_pair_id, str_to_felt
from pragma.publisher.fetchers.defillama import DefillamaFetcher
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

load_dotenv()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


ETH_PAIR = str_to_felt("ETH/USD")
SUPPORTED_ASSETS = [("ETH", "STRK"), ("STRK", "USD")]


class StarknetAMMFetcher(PublisherInterfaceT):
    client: PragmaClient
    EKUBO_PUBLIC_API: str = "https://goerli-api.ekubo.org"
    EKUBO_CORE_CONTRACT: str = (
        "0x031e8a7ab6a6a556548ac85cbb8b5f56e8905696e9f13e9a858142b8ee0cc221"
    )
    JEDISWAP_ETH_STRK_POOL: str = (
        "0x4e021092841c1b01907f42e7058f97e5a22056e605dce08a22868606ad675e0"
    )

    PRAGMA_ORACLE_CONTRACT: str = (
        "0x6df335982dddce41008e4c03f2546fa27276567b5274c7d0c1262f3c2b5d167"
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
    ETH_DECIMALS: int = 8
    STRK_DECIMALS: int = 8

    SOURCE = "STARKNET"

    ETH_USD = [PRAGMA_ALL_ASSETS[4]]

    publisher: str

    def __init__(self, assets: List[PragmaAsset], publisher, client=None):
        self.assets = assets
        self.publisher = publisher
        self.client = client or PragmaClient(network="testnet")

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
                    f"Error: Unable to retrieve data, status code {resp.status}"
                )

    async def on_fetch_ekubo_price(self) -> float:
        call = self.prepare_call()
        pool_info = await self.client.full_node_client.call_contract(call)
        sqrt_ratio = pool_info[0]
        if sqrt_ratio == 0:
            logger.error("Ekubo: Pool is empty")
        return (
            (sqrt_ratio / 2**128) ** 2 * 10 * (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    def on_fetch_ekubo_price_sync(self) -> float:
        call = self.prepare_call()
        pool_info = self.client.full_node_client.call_contract_sync(call)
        sqrt_ratio = pool_info[0]
        if sqrt_ratio == 0:
            logger.error("Ekubo: Pool is empty")
        return (
            (sqrt_ratio / 2**128) ** 2 * 10 * (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    async def on_fetch_jedi_price(self, session: ClientSession) -> float:
        call = Call(
            to_addr=self.JEDISWAP_ETH_STRK_POOL,
            selector=get_selector_from_name("get_reserves"),
            calldata=[],
        )
        async with session:
            reserves_infos = await self.client.full_node_client.call_contract(call)
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
        reserves_infos = self.client.full_node_client.call_contract_sync(call)
        token_0_reserve = reserves_infos[0] + reserves_infos[1] * 2**128
        token_1_reserve = reserves_infos[2] + reserves_infos[3] * 2**128
        if token_0_reserve == 0 or token_1_reserve == 0:
            logger.error("JediSwap: Pool is empty")
        return (
            token_1_reserve
            / token_0_reserve
            * 10 ** (self.ETH_DECIMALS - self.STRK_DECIMALS)
        )

    async def _fetch_strk(self, asset, session: ClientSession) -> SpotEntry:
        if asset["pair"] == ("ETH", "STRK"):
            # ekubo_price = await self.on_fetch_ekubo_price()
            ekubo_price = (
                await self.off_fetch_ekubo_price(asset, session)
                if isinstance(await self.off_fetch_ekubo_price(asset, session), float)
                else None
            )
            jedi_swap_price = await self.on_fetch_jedi_price(session)
            if ekubo_price is not None and jedi_swap_price is not None:
                return self._construct(asset, (ekubo_price + jedi_swap_price) / 2)
            elif ekubo_price is not None:
                return self._construct(asset, ekubo_price)
            elif jedi_swap_price is not None:
                return self._construct(asset, jedi_swap_price)
            else:
                logger.error("Both ekubo_price and jedi_swap_price are null")
                return PublisherFetchError("Both prices are unavailable")

        elif asset["pair"] == ("STRK", "USD"):
            eth_usd_entry = await self.client.get_spot(ETH_PAIR)
            # ekubo_price = await self.on_fetch_ekubo_price()
            ekubo_price = (
                await self.off_fetch_ekubo_price(asset, session)
                if isinstance(await self.off_fetch_ekubo_price(asset, session), float)
                else None
            )
            eth_usd_price = eth_usd_entry.price / (10**eth_usd_entry.decimals)
            jedi_swap_price = await self.on_fetch_jedi_price(session)
            if ekubo_price is not None and jedi_swap_price is not None:
                price = eth_usd_price / ((ekubo_price + jedi_swap_price) / 2)
                return self._construct(asset, price)
            elif ekubo_price is not None:
                price = eth_usd_price / ekubo_price
                return self._construct(asset, price)
            elif jedi_swap_price is not None:
                price = eth_usd_price / jedi_swap_price
                return self._construct(asset, price)
            else:
                logger.error("Both ekubo_price and jedi_swap_price are null")
                return PublisherFetchError("Both prices are unavailable")
        else:
            logger.error("Pair not available for the Starknet fetcher")
            return PublisherFetchError("Pair not available for the Starknet fetcher")

    def _fetch_strk_sync(self, asset) -> SpotEntry:
        if asset["pair"] == ("ETH", "STRK"):
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

        # TODO(#65): Handle sync version of the oracle mixin before uncommenting this part
        # elif asset["pair"] == ("STRK", "USD"):
        #     eth_usd_entry =  self.client.get_spot_sync(ETH_PAIR)
        #     # ekubo_price = await self.on_fetch_ekubo_price()
        #     ekubo_price = (
        #         self.off_fetch_ekubo_price_sync(asset)
        #         if isinstance(self.off_fetch_ekubo_price_sync(asset), float)
        #         else None
        #     )
        #     eth_usd_price = eth_usd_entry.price / (10 ** self.ETH_USD[0]["decimals"])
        #     jedi_swap_price = self.on_fetch_jedi_price_sync()
        #     if ekubo_price is not None and jedi_swap_price is not None:
        #         price = eth_usd_price / ((ekubo_price + jedi_swap_price) / 2)
        #         return self._construct(asset, price)
        #     elif ekubo_price is not None:
        #         price = eth_usd_price / ekubo_price
        #         return self._construct(asset, price)
        #     elif jedi_swap_price is not None:
        #         price = eth_usd_price / jedi_swap_price
        #         return self._construct(asset, price)
        #     else:
        #         logger.error("Both ekubo_price and jedi_swap_price are null")
        #         return PublisherFetchError("Both prices are unavailable")
        else:
            logger.error("Pair not available for the Starknet fetcher")
            return PublisherFetchError("Pair not available for the Starknet fetcher")

    def format_url(self, quote_asset, base_asset, time=None):
        if time:
            return f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}?atTime={time}&period=3600"
        else:
            return (
                f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}?period=3600"
            )

    async def fetch(self, session: ClientSession) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT" and asset["pair"] in SUPPORTED_ASSETS:
                entries.append(asyncio.ensure_future(self._fetch_strk(asset, session)))
            else:
                logger.debug(
                    f"Skipping StarknetAMM for non ETH or non STRK pair: {asset}"
                )

        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[SpotEntry]:
        entries = []
        for asset in self.assets:
            if asset["type"] == "SPOT" and asset["pair"] in SUPPORTED_ASSETS:
                entries.append(self._fetch_strk_sync(asset))
            else:
                logger.debug(
                    f"Skipping StarknetAMM for non ETH or non STRK pair: {asset}"
                )
        return entries

    def _construct(self, asset, result) -> SpotEntry:
        price_int = int(result * (10 ** asset["decimals"]))
        return SpotEntry(
            pair_id=currency_pair_to_pair_id(*asset["pair"]),
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )


# async def f1():
#     fetcher = StarknetAMMFetcher(PRAGMA_ALL_ASSETS, "PRAGMA")
#     async with ClientSession() as session:
#         price1 = await fetcher.fetch(session)

#     return price1

# def f2():
#     fetcher = StarknetAMMFetcher(PRAGMA_ALL_ASSETS, "PRAGMA")
#     price2 = fetcher.fetch_sync()
#     return price2

# # Run the main function in the asyncio event loop
# price1= asyncio.run(f1())
# price2 = f2()
# print(f"printaefeafe {price1}")
# print(price2)
