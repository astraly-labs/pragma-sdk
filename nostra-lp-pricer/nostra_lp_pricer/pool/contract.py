
from nostra_lp_pricer.types import Network, Reserves, POOL_ABI
from nostra_lp_pricer.client import get_contract
from typing import Dict


class PoolContract:
    """
    Interface to query basic configuration parameter from a given pool contract
    """
    def __init__(self, network: Network, address: str):
        self.network = network
        self.address = address
        self.contract = get_contract(network, int(address, 16), POOL_ABI)

    async def fetch_data(self) -> Dict:
        """Fetches basic pool data like name, symbol, decimals, and tokens."""
        try:
            name = await self.contract.functions['name'].call()
            symbol = await self.contract.functions['symbol'].call()
            decimals = await self.contract.functions['decimals'].call()
            token_0 = await self.contract.functions['token_0'].call()
            token_1 = await self.contract.functions['token_1'].call()

            return {
                "address": self.address,
                "name": name,
                "symbol": symbol,
                "decimals": decimals,
                "token_0": token_0,
                "token_1": token_1
            }
        except Exception as e:
            print(f"Error fetching contract data from {self.address}: {e}")
            return {"address": self.address, "error": str(e)}

    async def get_reserves(self) -> Reserves:
        """Fetches reserves from the pool."""
        return await self.contract.functions['get_reserves'].call()

    async def get_total_supply(self) -> int:
        """Fetches the total supply from the pool."""
        return await self.contract.functions['total_supply'].call()

    async def get_token_0(self) -> int:
        """Fetches the token 0 address from the pool."""
        return await self.contract.functions['token_0'].call()
    
    async def get_token_1(self) -> int: 
        """Fetches the token 1 address from the pool."""
        return await self.contract.functions['token_1'].call()