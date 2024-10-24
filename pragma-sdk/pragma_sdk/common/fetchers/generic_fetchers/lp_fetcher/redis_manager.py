from redis import Redis

from typing import List, Optional

from pragma_sdk.onchain.types.types import NetworkName
from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.lp_contract import Reserves


class LpRedisManager:
    """
    Class responsible of storing the 

    The current layout is:

        ├── mainnet
        │   └── 0x068cfffac83830edbc3da6f13a9aa19266b3f5b677a57c58d7742087cf439fdd
        │       ├── reserves
        │       └── total_supply
        └── sepolia
             └── (...)
    """

    client: Redis
    time_to_expire: int

    def __init__(self, host: str, port: str, time_to_expire: int = 24 * 60 * 60):
        self.client = Redis(host=host, port=port)
        self.time_to_expire = time_to_expire

    def store_pool_data(
        self,
        network: NetworkName,
        pool_address: str,
        reserves: Reserves,
        total_supply: int,
    ) -> bool:
        return all(
            [
                self._store_reserves(
                    network,
                    pool_address,
                    reserves,
                ),
                self._store_total_supply(
                    network,
                    pool_address,
                    total_supply,
                )
            ]
        )

    def _store_reserves(
        self,
        network: NetworkName,
        pool_address: str,
        reserves: Reserves,
    ) -> bool:
        key = self._get_key(network, pool_address, "reserves")
        res = self.client.json().set(key, "$", reserves)
        res_expire = self.client.expire(key, self.time_to_expire)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res and res_expire)

    def _store_total_supply(
        self,
        network: NetworkName,
        pool_address: str,
        total_supply: int,
    ) -> bool:
        key = self._get_key(network, pool_address, "total_supply")
        res = self.client.json().set(key, "$", total_supply)
        res_expire = self.client.expire(key, self.time_to_expire)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res and res_expire)

    def get_latest_n_reserves(
        self,
        network: NetworkName,
        pool_address: str,
        n: int = 1,
    ) -> List[Reserves]:
        """
        Get the latest N reserve entries for a specific pool.
        
        Args:
            network: The network name
            pool_address: The pool address
            n: Number of latest entries to retrieve (default=1)
            
        Returns:
            List of the latest N reserve entries. Returns empty list if no data found.
            The most recent entry is at index 0.
        """
        if n < 1:
            raise ValueError("n must be a positive integer")
            
        key = self._get_key(network, pool_address, "reserves")
        result = self.client.json().get(key)

        if not result:
            return []
            
        if not isinstance(result, list):
            return [result] if result else []
            
        return result[max(-n, -len(result)):][::-1]

    def get_latest_n_total_supply(
        self,
        network: NetworkName,
        pool_address: str,
        n: int = 1,
    ) -> List[int]:
        """
        Get the latest N total supply entries for a specific pool.
        
        Args:
            network: The network name
            pool_address: The pool address
            n: Number of latest entries to retrieve (default=1)
            
        Returns:
            List of the latest N total supply entries. Returns empty list if no data found.
            The most recent entry is at index 0.
        """
        key = self._get_key(network, pool_address, "total_supply")
        result = self.client.json().get(key)
        
        if not result:
            return []
            
        # If we have a single result and n=1, wrap it in a list
        if not isinstance(result, list):
            return [result] if result else []
            
        # Return up to n most recent entries, most recent first
        return result[-n:][::-1]

    def _get_key(
        self,
        network: NetworkName,
        pool_address: str,
        key: str,
    ) -> str:
        return f"{network}/{pool_address}/{key}"
