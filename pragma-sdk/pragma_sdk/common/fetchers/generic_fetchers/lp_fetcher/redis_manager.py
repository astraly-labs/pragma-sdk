import logging

from typing import List

from redis import Redis

from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.lp_contract import Reserves
from pragma_sdk.onchain.types import Network

logger = logging.getLogger(__name__)

# Maximum number of values
LISTS_MAX_VALUES = 480

# The data will be erased after 1 hour.
# We use it to automatically prune data that is too old. Used because if the publisher
# crash for some hours and restart, we don't want to compute prices on outdated data.
DEFAULT_TIME_TO_LIVE = 3600


class LpRedisManager:
    """
    Class responsible of storing LP data using Redis Lists for chronological order.

    The current layout is:
        ├── mainnet
        │   └── 0x068c...
        │       ├── reserves: [reserves_0, reserves_1, ..., reserves_N]
        │       └── total_supply: [total_supply_0, total_supply_1, ..., total_supply_N]
        └── sepolia
             └── (...)
    """

    client: Redis
    time_to_live: int

    def __init__(self, host: str, port: str, time_to_tive: int = DEFAULT_TIME_TO_LIVE):
        self.client = Redis(host=host, port=port)
        self.time_to_live = time_to_tive

    def store_pool_data(
        self,
        network: Network,
        pool_address: str,
        reserves: Reserves,
        total_supply: int,
    ) -> bool:
        """Store pool data using Redis Lists maintaining insertion order."""
        try:
            with self.client.pipeline() as pipe:
                # Store reserves
                reserves_key = self._get_key(network, pool_address, "reserves")
                pipe.lpush(reserves_key, self._pack_reserves(reserves))
                pipe.ltrim(reserves_key, 0, LISTS_MAX_VALUES - 1)
                pipe.expire(reserves_key, self.time_to_live)

                # Store total supply
                total_supply_key = self._get_key(network, pool_address, "total_supply")
                pipe.lpush(total_supply_key, str(total_supply))
                pipe.ltrim(total_supply_key, 0, LISTS_MAX_VALUES - 1)
                pipe.expire(total_supply_key, self.time_to_live)

                results = pipe.execute()
                return all(r is not None for r in results)
        except Exception as e:
            logger.error(f"Error storing pool data: {e}")
            return False

    def get_latest_n_reserves(
        self,
        network: Network,
        pool_address: str,
        n: int = 1,
    ) -> List[Reserves]:
        """
        Get the latest N reserve entries in chronological order (newest first).
        """
        if n < 1:
            raise ValueError("n must be a positive integer")
        n = min(n, LISTS_MAX_VALUES)

        key = self._get_key(network, pool_address, "reserves")
        results: List[bytes] = self.client.lrange(key, 0, n - 1)  # type: ignore[assignment]
        return [self._unpack_reserves(r.decode()) for r in results]

    def get_latest_n_total_supply(
        self,
        network: Network,
        pool_address: str,
        n: int = 1,
    ) -> List[int]:
        """
        Get the latest N total supply entries in chronological order (newest first).
        """
        if n < 1:
            raise ValueError("n must be a positive integer")
        n = min(n, LISTS_MAX_VALUES)

        key = self._get_key(network, pool_address, "total_supply")
        results: List[bytes] = self.client.lrange(key, 0, n - 1)  # type: ignore[assignment]

        return [int(v.decode()) for v in results]

    def _get_key(
        self,
        network: Network,
        pool_address: str,
        key: str,
    ) -> str:
        """Generate Redis key using proper Redis key naming conventions."""
        return f"{network}:{pool_address}:{key}"

    def _pack_reserves(self, reserves: Reserves) -> str:
        """Pack two integers into a compact string representation."""
        return f"{reserves[0]}:{reserves[1]}"

    def _unpack_reserves(self, packed: str) -> Reserves:
        """Unpack string representation back into two integers."""
        r0, r1 = packed.split(":")
        return (int(r0), int(r1))
