
import asyncio
from typing import Optional, List, Dict
import yaml
from nostra_lp_pricer.types import Network, POOL_ABI
from nostra_lp_pricer.client import get_contract,get_account
import json
from nostra_lp_pricer.pool_data_store import PoolDataStore
import time


async def fetch_contract_data(network: Network, contract_address: str ) -> Dict:
    """
    Fetch data from the IPool contract at the given address.
    
    Args:
        client: Starknet GatewayClient instance.
        contract_address: The address of the pool contract.

    Returns:
        A dictionary containing the configuration fetched from the contract.
    """
        # Load the contract
    contract = get_contract(network, int(contract_address, 16))
    
    # Fetch contract information using the IPool methods
    try:
        name = await contract.functions['name'].call()
        symbol = await contract.functions['symbol'].call()
        decimals = await contract.functions['decimals'].call()
        token_0 = await contract.functions['token_0'].call()
        token_1 = await contract.functions['token_1'].call()

        return {
            "address": contract.address,
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "token_0": token_0,
            "token_1": token_1
        }
    
    except Exception as e:
        print(f"Error fetching contract data from {contract_address}: {e}")
        return {"address": contract_address, "error": str(e)}



def convert_tuples_to_lists(data):
    """
    Recursively converts tuples to lists in the given data structure.
    """
    if isinstance(data, tuple):
        return list(data)
    elif isinstance(data, dict):
        return {key: convert_tuples_to_lists(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_tuples_to_lists(item) for item in data]
    return data

def load_pool_addresses_from_yaml(file_path: str) -> List[str]:
    """
    Load pool addresses from a YAML configuration file.
    
    Args:
        file_path: Path to the YAML file containing pool addresses.

    Returns:
        A list of pool addresses (strings).
    """
    with open(file_path, "r") as file:
        config = yaml.safe_load(file)
        return config.get("pool_addresses", [])


async def fetch_all_pools(network: Network, file_path: str) -> List[Dict]:
    """
    Fetch the configuration from all pool contracts listed in the YAML file.
    
    Args:
        file_path: Path to the YAML file containing pool addresses.

    Returns:
        A list of dictionaries containing the data fetched from each contract.
    """
    # Load pool addresses from YAML file
    pool_addresses = load_pool_addresses_from_yaml(file_path)

    # Starknet Gateway Client

    client = get_account(network)

    # Fetch data for all pool addresses asynchronously
    results = await asyncio.gather(*(fetch_contract_data(network, address) for address in pool_addresses))

    return results


def save_results_to_json(data: List[Dict], file_path: str) -> None:
    """
    Save the fetched pool configuration to a YAML file.
    
    Args:
        results: The list of results containing pool configuration data.
        output_path: The file path to save the YAML file to.
    """
    data = convert_tuples_to_lists(data)
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

async def fetch_and_store_data(pool_store: PoolDataStore, pool_contract, fetch_interval: int):
    while True:
        try:
            # Fetch total supply and reserves from the contract
            total_supply = await pool_contract.functions['total_supply'].call()
            reserves = await pool_contract.functions['get_reserves'].call()

            # Append the data to the respective deques
            pool_store.append_total_supply(total_supply)
            pool_store.append_reserves(reserves)

            print(f"Stored new data for pool at {time.time()}")
        except Exception as e:
            print(f"Error fetching data: {e}")

        # Wait for the next fetch
        await asyncio.sleep(fetch_interval)


async def calculate_and_push_median(pool_store: PoolDataStore, pool_contract, push_interval: int):
    while True:
        try:
            # Calculate median for total supply and reserves
            median_supply = pool_store.calculate_median_supply()
            median_reserves = pool_store.calculate_median_reserves()

            print(f"Calculated median - Supply: {median_supply}, Reserves: {median_reserves}")

        #     # Push the calculated values to the on-chain contract
        #     await pool_contract.push_price_to_contract(median_supply, median_reserves)

            print(f"Pushed median data to on-chain contract at {time.time()}")
        except Exception as e:
            print(f"Error pushing data to contract: {e}")

        # Wait for the next push
        await asyncio.sleep(push_interval)




# Main entry function
async def main():
    # File paths
    input_yaml = "pool_addresses.yaml"  # Input YAML file containing the list of pool addresses
    output_json = "pool_configs.json"   # Output JSON file to store the pool configurations
    network = "sepolia"


    pool_addresses = load_pool_addresses_from_yaml(input_yaml)
     # Initialize pool data stores (assuming 10-minute data storage)
    pool_stores = {address: PoolDataStore(max_age=600) for address in pool_addresses}
    
    pool_contracts = {address: get_contract(network,address) for address in pool_addresses}

    tasks = []
    for address, pool_contract in pool_contracts.items():
        pool_store = pool_stores[address]
        
        # Fetch data every minute and calculate/push every minute as well
        tasks.append(fetch_and_store_data(pool_store, pool_contract, fetch_interval=60))
        tasks.append(calculate_and_push_median(pool_store, pool_contract, push_interval=60))

    await asyncio.gather(*tasks)



if __name__ == "__main__":
    asyncio.run(main())
