

from nostra_lp_pricer.pool.data_store import PoolDataStore
from nostra_lp_pricer.pool.contract import PoolContract
from nostra_lp_pricer.client import get_contract
from nostra_lp_pricer.types import PRICER_ABI
from starknet_py.contract import InvokeResult
from typing import List
import asyncio
import time

class PoolDataFetcher:
    """
    Interface to periodically fetch and store data in the Doubly Ended Queue (Deque), see data_store.py for reference
    """
    def __init__(self, pool_store: PoolDataStore, pool_contract: PoolContract, fetch_interval: int):
        self.pool_store = pool_store
        self.pool_contract = pool_contract
        self.fetch_interval = fetch_interval

    async def fetch_and_store_data(self):
        """Periodically fetches and stores data."""
        while True:
            try:
                total_supply = await self.pool_contract.get_total_supply()
                reserves = await self.pool_contract.get_reserves()
                self.pool_store.append_total_supply(total_supply[0])
                self.pool_store.append_reserves(reserves[0])
                print(f"Stored new data for pool at {time.time()}, with total supply: {total_supply[0]} and reserves: {reserves[0]}")
            except Exception as e:
                print(f"Error fetching data: {e}")
            await asyncio.sleep(self.fetch_interval)


class PricePusher: 
    """
    Interface to interact with the LP pricer contract. Used to push the LP price onchain
    """

    def __init__(self, network, address):
        self.network = network
        self.contract = get_contract(network, int(address, 16), PRICER_ABI)
    
    async def push_price(self, pool_address: int, price: int) -> InvokeResult: 
        """Push the desired LP price onchain"""
        invocation =  await self.contract.functions['push_price'].invoke(pool_address,price)
        return invocation
    

    async def get_registered_pools(self) -> List[int]: 
        """Get the list of registered pools on the onchain pricer"""
        return await self.contract.functions["get_pools"].call()
    
    async def add_pools(self, pools: List[int]): 
        """Add a list of pools to the pricer contract. Revert if one pool is already registered
        Args: 
            pools: The list of pools addresses to add(int)
        """
        invocation = await self.contract.functions["add_pools"].invoke(pools)
        return invocation

    async def register_missing_pools(self, pool_manager, onchain_registered_pools):
        """
        Registers pools that are present in the configuration but not yet registered on-chain.

        Args:
            price_pusher: The instance of the contract responsible for pushing prices on-chain.
            pool_manager: The instance managing pool contracts and addresses.
            onchain_registered_pools: The list of pools already registered on-chain.
        """
        pool_contracts = pool_manager._load_pools()

        # Build a list of pool addresses from the YAML configuration
        yaml_pool_addresses = [int(pool_contract.address, 16) for pool_contract in pool_contracts]

        # Determine which addresses are not registered on-chain
        not_registered_addresses = [addr for addr in yaml_pool_addresses if addr not in onchain_registered_pools]
        # If there are any addresses to be registered, call the add_pools method
        if not_registered_addresses:
            invocation = await self.add_pools(not_registered_addresses)
            await invocation.wait_for_acceptance()
            print(f"Registered missing pools: {not_registered_addresses}")
        else:
            print("No new pools to register.")
