from typing import Optional

from redis import Redis
from starknet_py.hash.hash_method import HashMethod
from starknet_py.utils.merkle_tree import MerkleTree

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import (
    LatestData,
    CurrenciesOptions,
    OptionData,
)


class RedisManager:
    client: Redis

    def __init__(self, host: str, port: str):
        self.client = Redis(host=host, port=port)

    def store_latest_data(self, latest_data: Optional[LatestData]) -> None:
        if latest_data is None:
            return
        last_merkle_tree = latest_data.merkle_tree.as_dict()
        self.client.json().set("last_merkle_tree", "$", last_merkle_tree)
        last_options = {
            currency: [option.as_dict() for option in options]
            for currency, options in latest_data.options.items()
        }
        self.client.json().set("last_options", "$", last_options)

    def get_options(self) -> Optional[CurrenciesOptions]:
        response = self.client.json().get("last_options", "$")
        if len(response) == 0:
            return None
        options = {
            currency: [OptionData(**option) for option in options]
            for currency, options in response[0].items()
        }
        return options

    def get_merkle_tree(self) -> Optional[MerkleTree]:
        response = self.client.json().get("last_merkle_tree", "$")
        if len(response) == 0:
            return None
        return MerkleTree(
            leaves=response[0]["leaves"], hash_method=HashMethod(response[0]["hash_method"].lower())
        )
