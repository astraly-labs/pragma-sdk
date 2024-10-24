import asyncio
from nostra_lp_pricer.pool.data_store import PoolDataStore
from nostra_lp_pricer.pool.manager import PoolManager
from nostra_lp_pricer.pool.contract import PoolContract
from nostra_lp_pricer.pool.data_fetcher import PoolDataFetcher
from nostra_lp_pricer.pricing.median_calculator import MedianCalculator
from nostra_lp_pricer.oracle.oracle import Oracle
from nostra_lp_pricer.types import FETCH_INTERVAL,PUSH_INTERVAL

# Main entry function
async def main():
    # File paths
    input_yaml = "addresses.yaml"  # Input YAML file containing the list of pool addresses
    output_json = "pool_configs.json"   # Output JSON file to store the pool configurations
    network = "sepolia"


    pool_manager = PoolManager(network,input_yaml)

    pool_contracts = pool_manager._load_pools()


     # Initialize pool data stores (assuming 10-minute data storage)
    pool_stores = {pool.address: PoolDataStore(max_age=600) for pool in pool_contracts}


    tasks = []
    for pool_contract in pool_contracts:
        token_0 = await pool_contract.get_token_0()
        token_1 =  await pool_contract.get_token_1()
        print(token_1)
        pool_store = pool_stores[pool_contract.address]
        data_fetcher = PoolDataFetcher(pool_store, pool_contract, FETCH_INTERVAL)
        oracle = Oracle(network)
        median_calculator = MedianCalculator(pool_store, pool_contract,oracle,PUSH_INTERVAL)
        # Fetch data every minute and calculate/push every minute as well
        tasks.append(data_fetcher.fetch_and_store_data())
        tasks.append(median_calculator.calculate_and_push_median((token_0[0], token_1[0])))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
