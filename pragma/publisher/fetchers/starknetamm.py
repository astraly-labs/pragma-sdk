import requests
import asyncio
import time 
from pragma.publisher.types import PublisherFetchError
from typing import Union, List
from starknet_py.net.client_models import Call
from starknet_py.net.client import Client
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.account.account import Account
from starknet_py.hash.selector import get_selector_from_name
import math
import os 
from dotenv import load_dotenv
from pragma.core.types import get_client_from_network

load_dotenv()
WALLET_ADDRESS: str = '0x0092cC9b7756E6667b654C0B16d9695347AF788EFBC00a286efE82a6E46Bce4b'
PRIVATE_KEY: str = os.getenv("PRIVATE_KEY")
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

class StarknetAMMFetcher: 
    client = get_client_from_network("mainnet")
    EKUBO_PUBLIC_API: str = 'https://mainnet-api.ekubo.org'
    EKUBO_CORE_CONTRACT: str = '0x031e8a7ab6a6a556548ac85cbb8b5f56e8905696e9f13e9a858142b8ee0cc221'
    JEDISWAP_ETH_USDC_POOL: str = '0x04d0390b777b424e43839cd1e744799f3de6c176c7e32c1812a41dbd9c19db6a'
    # Parameters for the pool 

    # These are the parameters of the most used pool in Ekubo for the testing pair ETH/USDC
    POOL_FEE = 0.0005 # 0.05%  
    TICK_SPACING = 0.001 # 0.1%
    TICK_BASE = 1.000001  
    POOL_EXTENSION = 0

    STRK_ADDRESS: str = ''  
    ETH_ADDRESS: str = '0x049D36570D4e46f48e99674bd3fcc84644DdD6b96F7C741B1562B82f9e004dC7' 
    USDC_ADDRESS: str = '0x053c91253bc9682c04929ca02ed00b3e423f6710d2ee7e0d5ebb06f3ecf368a8' #for testing purpose 
    ETH_DECIMALS: int = 18 
    USDC_DECIMALS: int = 6

   
    # Version1: fetching the price using the Ekubo API 
    async def off_fetch_ekubo_price(self) -> Union[float, PublisherFetchError]:
        url = f"{self.EKUBO_PUBLIC_API}/price/{self.ETH_ADDRESS}/{self.USDC_ADDRESS}"
        try: 
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()['price']
            else: 
                return f"Error: Unable to retrieve data, status code {response.status_code}"
        except Exception as e:
            return f"Error: {e}"


    async def on_fetch_ekubo_price(self) -> float:
        token_0, token_1 = min(self.ETH_ADDRESS, self.USDC_ADDRESS), max(self.ETH_ADDRESS, self.USDC_ADDRESS)
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
        assert sqrt_ratio != 0, " sqrt_ratio is null"
        return (sqrt_ratio/2**128)**2 * 10*(self.ETH_DECIMALS - self.USDC_DECIMALS)

    
    async def on_fetch_jedi_price(self) -> float:
        call = Call(
            to_addr=self.JEDISWAP_ETH_USDC_POOL,
            selector=get_selector_from_name("get_reserves"),
            calldata=[],
        )
        reserves_infos = await self.client.call_contract(call)
        token_0_reserve = reserves_infos[0] + reserves_infos[1] * 2**128
        token_1_reserve = reserves_infos[2] + reserves_infos[3] * 2**128
        return token_1_reserve/token_0_reserve * 10**(self.ETH_DECIMALS - self.USDC_DECIMALS)


    async def fetch_strk_price(self) -> Union[float, PublisherFetchError]:
        ekubo_price = await self.off_fetch_ekubo_price()
        jedi_swap_price = await self.on_fetch_jedi_price()
        # TODO: operation with the elements



async def main():
    fetcher = StarknetAMMFetcher()
    price = await fetcher.on_fetch_jedi_price()
    print(price)

# Run the main function in the asyncio event loop
asyncio.run(main())