

from nostra_lp_pricer.pool.data_store import PoolDataStore
from nostra_lp_pricer.pool.contract import PoolContract
import asyncio
import time

class PoolDataFetcher:
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

