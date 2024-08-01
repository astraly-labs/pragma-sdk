from typing import Optional, Literal

from redis import Redis
from starknet_py.hash.hash_method import HashMethod
from starknet_py.utils.merkle_tree import MerkleTree

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import (
    LatestData,
    CurrenciesOptions,
    OptionData,
)

from merkle_maker.serializers import merkle_tree_to_dict


class RedisManager:
    client: Redis

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

    def store_latest_data(
        self,
        network: Literal["mainnet", "sepolia"],
        latest_data: Optional[LatestData],
    ) -> bool:
        if latest_data is None:
            return False
        return all(
            [
                self._store_latest_merkle_tree(network, latest_data.merkle_tree),
                self._store_latest_options(network, latest_data.options),
            ]
        )

    def get_options(self, network: Literal["mainnet", "sepolia"]) -> Optional[CurrenciesOptions]:
        key = self._get_key(network, "last_options")
        response = self.client.json().get(key, "$")
        if response is None or len(response) == 0:
            return None
        options = {
            currency: [OptionData(**option) for option in options]
            for currency, options in response[0].items()
        }
        return options

    def get_merkle_tree(self, network: Literal["mainnet", "sepolia"]) -> Optional[MerkleTree]:
        key = self._get_key(network, "last_merkle_tree")
        response = self.client.json().get(key, "$")
        if response is None or len(response) == 0:
            return None
        return MerkleTree(
            leaves=response[0]["leaves"],
            hash_method=HashMethod(response[0]["hash_method"].lower()),
        )

    def _store_latest_merkle_tree(
        self,
        network: Literal["mainnet", "sepolia"],
        merkle_tree: MerkleTree,
    ) -> bool:
        last_merkle_tree = merkle_tree_to_dict(merkle_tree)

        key = self._get_key(network, "last_merkle_tree")
        res = self.client.json().set(key, "$", last_merkle_tree)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res)

    def _store_latest_options(
        self,
        network: Literal["mainnet", "sepolia"],
        options: CurrenciesOptions,
    ) -> bool:
        last_options = {
            currency: [option.as_dict() for option in options]
            for currency, options in options.items()
        }

        key = self._get_key(network, "last_options")
        res = self.client.json().set(key, "$", last_options)

        # .set() returns a bool but is marked as Any by Mypy so we explicitely cast:
        # see: https://redis.io/docs/latest/develop/data-types/json/
        return bool(res)

    def _get_key(self, network: Literal["mainnet", "sepolia"], key: str) -> str:
        return f"{network}/{key}"
