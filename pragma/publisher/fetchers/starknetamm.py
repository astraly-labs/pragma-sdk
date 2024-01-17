import requests
import asyncio
import time 
import logging
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT
from typing import Union, List
from starknet_py.net.client_models import Call
from pragma.core.entry import SpotEntry
from pragma.core.assets import PragmaAsset, PragmaSpotAsset
from pragma.core.utils import currency_pair_to_pair_id
from starknet_py.hash.selector import get_selector_from_name
import math
import os 
from aiohttp import ClientSession
from pragma.core.assets import PRAGMA_ALL_ASSETS

from dotenv import load_dotenv
from pragma.core.types import get_client_from_network

load_dotenv()
WALLET_ADDRESS: str = '0x0092cC9b7756E6667b654C0B16d9695347AF788EFBC00a286efE82a6E46Bce4b'
PRIVATE_KEY: str = os.getenv("PRIVATE_KEY")
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class PoolKey: 
    # token0 is the the token with the smaller adddress (sorted by integer value)
    # token1 is the token with the larger address (sorted by integer value)
    # fee is specified as a 0.128 number, so 1% == 2**128 / 100
    # tick_spacing is the minimum spacing between initialized ticks, i.e. ticks that positions may use
    # extension is the address of a contract that implements additional functionality for the pool
    token_0: int
    token_1: int
    fee: int
    tick_spacing: int
    extension: int

    def __init__( 
        self,
        token_0: int,
        token_1: int,
        fee: int,
        tick_spacing: int,
        extension: int = 0,
    ): 
        self.token_0 = token_0
        self.token_1 = token_1
        self.fee = fee
        self.tick_spacing = tick_spacing
        self.extension = extension
    
    def serialize(self) -> List[str]:
        return [
            self.token_0,
            self.token_1,
            self.fee,
            self.tick_spacing,
            self.extension,
        ]
    def to_dict(self) -> dict: 
        return {
            "token_0": self.token_0,
            "token_1": self.token_1,
            "fee": self.fee,
            "tick_spacing": self.tick_spacing,
            "extension": self.extension,
        }
    def __repr__(self): 
        return f"PoolKey({self.token_0}, {self.token_1}, {self.fee}, {self.tick_spacing}, {self.extension})"

class StarknetAMMFetcher(PublisherInterfaceT): 
    client = get_client_from_network("testnet")
    EKUBO_PUBLIC_API: str = 'https://goerli-api.ekubo.org'
    EKUBO_CORE_CONTRACT: str = '0x031e8a7ab6a6a556548ac85cbb8b5f56e8905696e9f13e9a858142b8ee0cc221'
    JEDISWAP_STRK_ETH_POOL: str = '0x4e021092841c1b01907f42e7058f97e5a22056e605dce08a22868606ad675e0'
    # Parameters for the pool 

    # These are the parameters of the most used pool in Ekubo for the testing pair ETH/USDC
    POOL_FEE = 0.0005 # 0.05%  
    TICK_SPACING = 0.001 # 0.1%
    TICK_BASE = 1.000001  
    POOL_EXTENSION = 0

    STRK_ADDRESS: str = '0x04718f5a0fc34cc1af16a1cdee98ffb20c31f5cd61d6ab07201858f4287c938d'  
    ETH_ADDRESS: str = '0x049D36570D4e46f48e99674bd3fcc84644DdD6b96F7C741B1562B82f9e004dC7' 
    ETH_DECIMALS: int = 18 
    STRK_DECIMALS: int = 18

    SOURCE= "JEDISWAP,EKUBO"

    publisher: str
   
    def __init__(self, assets: List[PragmaAsset], publisher):
        self.assets = assets
        self.publisher = publisher
    
    # Version1: fetching the price using the Ekubo API 
    async def off_fetch_ekubo_price(self) -> Union[float, PublisherFetchError]:
        url = self.format_url(self.ETH_ADDRESS, self.STRK_ADDRESS)
        try: 
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()['price']
            else: 
                return f"Error: Unable to retrieve data, status code {response.status_code}"
        except Exception as e:
            return f"Error: {e}"


    async def on_fetch_ekubo_price(self) -> float:
        token_0, token_1 = min(self.ETH_ADDRESS, self.STRK_ADDRESS), max(self.ETH_ADDRESS, self.STRK_ADDRESS)
        fee = math.floor(self.POOL_FEE * 2**128)
        # An TICK_SPACING increaese of a price means the new price is price*(1+TICK_SPACING)
        # We want to know the number of tick for a price increase of TICK_SPACING
        # Since the tick spacing is represented as an exponent of TICK_BASE, we can use the logarithm to find the number of tick
        tick = round(math.log(1 + self.TICK_SPACING)/math.log(self.TICK_BASE))
        pool_key = PoolKey(int(token_0, 16), int(token_1, 16), int(fee), int(tick),int(self.POOL_EXTENSION))
        call = Call(
            to_addr=self.EKUBO_CORE_CONTRACT,
            selector=get_selector_from_name("get_pool_price"),
            calldata=pool_key.serialize(),
        )
        pool_info= await self.client.call_contract(call)
        sqrt_ratio = pool_info[0]
        if sqrt_ratio == 0:
            logger.error("Ekubo: Pool is empty")
        return (sqrt_ratio/2**128)**2 * 10*(self.ETH_DECIMALS - self.STRK_DECIMALS)

    
    async def on_fetch_jedi_price(self) -> float:
        call = Call(
            to_addr=self.JEDISWAP_STRK_ETH_POOL,
            selector=get_selector_from_name("get_reserves"),
            calldata=[],
        )
        reserves_infos = await self.client.call_contract(call)
        token_0_reserve = reserves_infos[0] + reserves_infos[1] * 2**128
        token_1_reserve = reserves_infos[2] + reserves_infos[3] * 2**128
        return token_1_reserve/token_0_reserve * 10**(self.ETH_DECIMALS - self.STRK_DECIMALS)


    async def fetch_strk_price(self) -> Union[float, PublisherFetchError]:
        ekubo_price = await self.on_fetch_ekubo_price()
        jedi_swap_price = await self.on_fetch_jedi_price()

        if ekubo_price is not None and jedi_swap_price is not None:
            return (ekubo_price + jedi_swap_price) / 2
        elif ekubo_price is not None:
            return ekubo_price
        elif jedi_swap_price is not None:
            return jedi_swap_price
        else:
            logger.error("Both ekubo_price and jedi_swap_price are null")
            return PublisherFetchError("Both prices are unavailable")
        

    def format_url(self, quote_asset, base_asset):
        url = f"{self.EKUBO_PUBLIC_API}/price/{base_asset}/{quote_asset}"
        return url

    async def fetch(
        self,
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        for asset in self.assets:
            if asset["type"] != "SPOT" or asset["pair"] != ("STRK", "ETH"):
                logger.debug(f"Skipping StarknetAMM for non STRK or non ETH pair: {asset}")
                continue
            entries.append(asyncio.ensure_future(self._construct(asset)))
        return await asyncio.gather(*entries, return_exceptions=True)

    def fetch_sync(self) -> List[Union[SpotEntry, PublisherFetchError]]:
        entries = []
        # for asset in self.assets:
        #     if asset["type"] != "SPOT" or asset["pair"] != ("STRK", "ETH"):
        #         logger.debug(f"Skipping StarknetAMM for non STRK or non ETH pair: {asset}")
        #         continue
        #     entries.append(self._construct(asset))
        return entries


    async def _construct(self, asset) -> SpotEntry:
        price = await self.fetch_strk_price()
        return SpotEntry(
            pair_id=currency_pair_to_pair_id(asset["pair"][0], asset["pair"][1]),
            price=price,
            timestamp=int(time.time()),
            source= self.SOURCE,
            publisher= self.publisher,
        )
    

async def main():
    fetcher = StarknetAMMFetcher(PRAGMA_ALL_ASSETS,"PRAGMA")
    price = await fetcher.fetch()
    print(price)

# Run the main function in the asyncio event loop
asyncio.run(main())