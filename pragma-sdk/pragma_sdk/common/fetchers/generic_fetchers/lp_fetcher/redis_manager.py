import logging

from typing import List, Any

from redis import Redis

from pragma_sdk.onchain.types.types import NetworkName
from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.lp_contract import Reserves

logger = logging.getLogger(__name__)

LISTS_MAX_VALUES = 480


class LpRedisManager:
    """
    Class responsible of storing the

    The current layout is:

        ├── mainnet
        │   └── 0x068cfffac83830edbc3da6f13a9aa19266b3f5b677a57c58d7742087cf439fdd
        │       ├── reserves: [reserves_0, reserves_1, ..., reserves_N]
        │       └── total_supply: [total_supply_0, total_supply_1, ..., total_supply_N]
        └── sepolia
             └── (...)
    """

    client: Redis
    time_to_expire: int

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

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
                ),
            ]
        )

    def _get(
        self,
        network: NetworkName,
        pool_address: str,
        key: str,
    ) -> Any:
        key = self._get_key(network, pool_address, key)
        response = self.client.json().get(key, "$")
        if response is None:
            return None
        return response

    def _store_reserves(
        self,
        network: NetworkName,
        pool_address: str,
        reserves: Reserves,
    ) -> bool:
        key = self._get_key(network, pool_address, "reserves")
        latest_value = self._get(network, pool_address, "reserves")

        if latest_value is None:
            latest_value = []
        elif len(latest_value) >= LISTS_MAX_VALUES:
            latest_value.pop(0)
        latest_value.append(reserves)

        res = self.client.json().set(key, "$", latest_value)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res)

    def _store_total_supply(
        self,
        network: NetworkName,
        pool_address: str,
        total_supply: int,
    ) -> bool:
        key = self._get_key(network, pool_address, "total_supply")
        latest_value = self._get(network, pool_address, "total_supply")

        if latest_value is None:
            latest_value = []
        elif len(latest_value) >= LISTS_MAX_VALUES:
            latest_value.pop(0)
        latest_value.append(total_supply)

        res = self.client.json().set(key, "$", latest_value)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res)

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
        if n > LISTS_MAX_VALUES:
            n = LISTS_MAX_VALUES

        key = self._get_key(network, pool_address, "reserves")
        result = self.client.json().get(key)

        if not result:
            return []

        if not isinstance(result, list):
            return [result] if result else []

        return result[max(-n, -len(result)) :][::-1]

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

        # If we have a single result and n=1, wrap it in a listc
        if not isinstance(result, list):
            return [result] if result else []

        # Return up to n most recent entries, most recent first
        return result[max(-n, -len(result)) :][::-1]

    def _get_key(
        self,
        network: NetworkName,
        pool_address: str,
        key: str,
    ) -> str:
        return f"{network}/{pool_address}/{key}"
