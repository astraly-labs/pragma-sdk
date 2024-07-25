from typing import Dict, Any
from redis import Redis
from pragma_sdk.common.types.merkle_tree import MerkleTree
from pragma_sdk.common.fetchers.generic_fetchers.deribit import CurrenciesOptions, OptionData


class RedisManager:
    client: Redis

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

    def store_merkle_tree(self, key: str, merkle_tree: MerkleTree):
        # Store leaves
        self.client.rpush(f"{key}:leaves", *merkle_tree.leaves)

        # Store levels
        for i, level in enumerate(merkle_tree.levels):
            self.client.rpush(f"{key}:level:{i}", *level)

        # Store root hash
        self.client.set(f"{key}:root", merkle_tree.root_hash)

        # Store number of levels (useful for reconstruction)
        self.client.set(f"{key}:level_count", len(merkle_tree.levels))

    def get_merkle_tree(self, key: str) -> MerkleTree:
        leaves = [int(leaf) for leaf in self.client.lrange(f"{key}:leaves", 0, -1)]
        root_hash = int(self.client.get(f"{key}:root"))
        level_count = int(self.client.get(f"{key}:level_count"))

        levels = []
        for i in range(level_count):
            level = [int(node) for node in self.client.lrange(f"{key}:level:{i}", 0, -1)]
            levels.append(level)

        # Recreate MerkleTree object
        # Note: This assumes you've modified MerkleTree to accept pre-computed levels and root_hash
        return MerkleTree(leaves=leaves, levels=levels, root_hash=root_hash)

    def store_options(self, key: str, options: CurrenciesOptions):
        for currency, option_list in options.items():
            currency_key = f"{key}:{currency}"
            option_dict = {
                option.instrument_name: self._serialize_option(option) for option in option_list
            }
            self.client.hmset(currency_key, option_dict)

    def get_options(self, key: str, currency: str) -> Dict[str, Dict[str, Any]]:
        currency_key = f"{key}:{currency}"
        raw_options = self.client.hgetall(currency_key)
        return {k.decode(): self._deserialize_option(v) for k, v in raw_options.items()}

    def _serialize_option(self, option: OptionData) -> str:
        return ",".join(
            map(
                str,
                [
                    option.instrument_name,
                    option.base_currency,
                    option.current_timestamp,
                    option.mark_price,
                ],
            )
        )

    def _deserialize_option(self, option_str: bytes) -> Dict[str, Any]:
        values = option_str.decode().split(",")
        return {
            "instrument_name": values[0],
            "base_currency": values[1],
            "current_timestamp": int(values[2]),
            "mark_price": float(values[3]),
        }
