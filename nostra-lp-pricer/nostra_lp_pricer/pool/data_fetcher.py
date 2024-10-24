

from nostra_lp_pricer.pool.data_store import PoolDataStore
from nostra_lp_pricer.pool.contract import PoolContract
from nostra_lp_pricer.client import get_contract
from nostra_lp_pricer.types import PRICER_ABI
from starknet_py.contract import InvokeResult
from typing import List,Union,Dict
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


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
            total_supply = await self.pool_contract.get_total_supply()
            reserves = await self.pool_contract.get_reserves()

            if total_supply is not None and "error" not in reserves:
                self.pool_store.append_total_supply(total_supply[0])
                self.pool_store.append_reserves(reserves[0])
                logger.info(f"Stored new data for pool at {time.time()}, with total supply: {total_supply[0]} and reserves: {reserves[0]}")
            else:
                logger.info(f"Error fetching data for pool at {self.pool_contract.address}: {total_supply.get('error')}, {reserves.get('error')}")

            await asyncio.sleep(self.fetch_interval)


class PricePusher: 
    """
    Interface to interact with the LP pricer contract. Used to push the LP price onchain
    """

    def __init__(self, network, address):
        self.network = network
        self.contract = get_contract(network, int(address, 16), PRICER_ABI)
    
    async def push_price(self, pool_address: int, price: int) -> Union[InvokeResult, Dict[str, str]]: 
        """Push the desired LP price onchain"""
        try: 
            invocation =  await self.contract.functions['push_price'].invoke(pool_address,price)
            return invocation
        except Exception as e: 
            logger.error(f"Error pushing price for pool: {pool_address}: {str(e)} ")
            return {"error": str(e)}    

    async def get_registered_pools(self) -> Union[List[int], Dict[str, str]]: 
        """Get the list of registered pools on the onchain pricer"""
        try: 
            return await self.contract.functions["get_pools"].call()
        except Exception as e: 
            logger.error(f"Error fetching the registered onchain pools: {str(e)}")
            return {"error": str(e)}    

    
    async def add_pools(self, pools: List[int]) -> Union[InvokeResult, Dict[str, str]]: 
        """Add a list of pools to the pricer contract. Revert if one pool is already registered
        Args: 
            pools: The list of pools addresses to add(int)
        """
        try:
            invocation = await self.contract.functions["add_pools"].invoke(pools)
            return invocation
        except Exception as e: 
            logger.error(f"Error adding pools: {str(e)} ")
            return {"error": str(e)}    
        
    
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
            logger.info(f"Registered missing pools: {not_registered_addresses}")
        else:
            logger.info("No new pools to register.")