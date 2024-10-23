import yaml 
from nostra_lp_pricer.types import Network
from typing import List, Dict
from nostra_lp_pricer.pool.contract import PoolContract
import asyncio
import json

class PoolManager:
    """
    Interface to load the configuration from the yaml file (the list of pool addresses and the lp pricer contract)
    """
    def __init__(self, network: Network, config_file: str):
        self.network = network
        self.config_file = config_file
        self.pools: List[PoolContract] = self._load_pools()

    def _load_pools(self) -> List[PoolContract]:
        """Loads pool addresses from the YAML configuration and initializes PoolContract objects."""
        with open(self.config_file, "r") as file:
            config = yaml.safe_load(file)
            pool_addresses = config.get("pool_addresses", [])
        return [PoolContract(self.network, address) for address in pool_addresses]

    async def fetch_all_pools(self) -> List[Dict]:
        """Fetches data from all pools asynchronously."""
        return await asyncio.gather(*(pool.fetch_data() for pool in self.pools))

    def save_to_json(self, data: List[Dict], output_file: str) -> None:
        """Saves pool data to a JSON file."""
        with open(output_file, 'w') as file:
            json.dump(self._convert_tuples_to_lists(data), file, indent=4)

    @staticmethod
    def _convert_tuples_to_lists(data):
        """Converts tuples to lists recursively in a data structure."""
        if isinstance(data, tuple):
            return list(data)
        elif isinstance(data, dict):
            return {key: PoolManager._convert_tuples_to_lists(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [PoolManager._convert_tuples_to_lists(item) for item in data]
        return data
