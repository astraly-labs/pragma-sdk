from typing import Optional, Dict, List, Any
from collections import defaultdict
from decimal import Decimal

from redis import Redis
from starknet_py.hash.hash_method import HashMethod
from starknet_py.utils.merkle_tree import MerkleTree

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import (
    LatestData,
    CurrenciesOptions,
    OptionData,
)

from pragma_sdk.onchain.types.types import NetworkName

from merkle_maker.serializers import serialize_merkle_tree

KEYS_TIME_TO_EXPIRE = 24 * 60 * 60  # 24 hours


class RedisManager:
    """
    Class responsible of storing the options data and the merkle tree used
    to generate the Merkle Root onchain that was published at a certain block.

    The current layout is:

        .
        ├── mainnet
        │   └── 64680
        │       ├── merkle_tree
        │       └── options
        │           ├── BTC-27DEC24-59000-C
        │           └── BTC-27SEP24-42000-P
        └── sepolia
            ├── 56777
            │   ├── merkle_tree
            │   └── options
            │       ├── BTC-27DEC24-59000-C
            │       └── BTC-27SEP24-42000-P
            └── 56778
                ├── merkle_tree
                └── options
                    ├── BTC-27DEC24-59000-C
                    └── BTC-27SEP24-42000-P

    - `merkle_tree` being the merkle tree used to generate the merkle root
      published on chain,
    - `options` being the directory containg the options. The option name
      is the instrument name.
    """

    client: Redis

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

    def store_block_data(
        self,
        network: NetworkName,
        block_number: int,
        latest_data: Optional[LatestData],
    ) -> bool:
        if latest_data is None:
            return False
        return all(
            [
                self._store_merkle_tree(
                    network,
                    block_number,
                    latest_data.merkle_tree,
                ),
                self._store_options(
                    network,
                    block_number,
                    latest_data.options,
                ),
            ]
        )

    def get_option(
        self,
        network: NetworkName,
        block_number: int,
        instrument_name: str,
    ) -> Optional[OptionData]:
        key = self._get_key(network, block_number, f"options/{instrument_name}")
        response = self.client.json().get(key, "$")
        if response is None or len(response) != 1:
            return None
        return OptionData(**(response[0]))

    def get_all_options(
        self,
        network: NetworkName,
        block_number: int,
    ) -> Optional[CurrenciesOptions]:
        # Get all keys for options at this block number
        all_options_pattern = self._get_key(network, block_number, "options/*")
        option_keys: Any = self.client.keys(all_options_pattern)

        if not option_keys:
            return None

        options: Dict[str, List[OptionData]] = defaultdict(list)
        for key in option_keys:
            option_dict = self.client.json().get(key)
            option_dict["mark_price"] = int(Decimal(option_dict["mark_price"]))
            if option_dict:
                option = OptionData(**option_dict)
                options[option.base_currency].append(option)

        return dict(options)

    def get_merkle_tree(
        self,
        network: NetworkName,
        block_number: int,
    ) -> Optional[MerkleTree]:
        key = self._get_key(network, block_number, "merkle_tree")
        response = self.client.json().get(key, "$")
        if response is None or len(response) == 0:
            return None
        leaves = [int(leaf, 16) for leaf in response[0]["leaves"]]
        return MerkleTree(
            leaves=leaves,
            hash_method=HashMethod(response[0]["hash_method"].lower()),
        )

    def _store_merkle_tree(
        self,
        network: NetworkName,
        block_number: int,
        merkle_tree: MerkleTree,
    ) -> bool:
        serialized_merkle_tree = serialize_merkle_tree(merkle_tree)

        key = self._get_key(network, block_number, "merkle_tree")
        res = self.client.json().set(key, "$", serialized_merkle_tree)
        res_expire = self.client.expire(key, KEYS_TIME_TO_EXPIRE)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res and res_expire)

    def _store_options(
        self,
        network: NetworkName,
        block_number: int,
        options: CurrenciesOptions,
    ) -> bool:
        for currency, option_list in options.items():
            for option in option_list:
                option_name = f"options/{option.instrument_name}"
                key = self._get_key(network, block_number, option_name)

                serialized_option = option.as_dict()
                res = self.client.json().set(key, "$", serialized_option)
                res_expire = self.client.expire(key, KEYS_TIME_TO_EXPIRE)

                # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
                # see: https://redis.io/docs/latest/develop/data-types/json/
                if not bool(res and res_expire):
                    # If we could not store something, we fail fast and exit the application.
                    # This should never happen, the only possible failures are:
                    # - connection to Redis is corrupted,
                    # - redis is full.
                    # For both cases, we have to handle this ourselves after crashing the app.
                    return False
        return True

    def _get_key(
        self,
        network: NetworkName,
        block_number: int,
        name: str,
    ) -> str:
        return f"{network}/{block_number}/{name}"
