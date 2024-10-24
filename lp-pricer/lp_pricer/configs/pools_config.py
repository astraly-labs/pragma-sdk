import yaml

from typing import List

from pydantic import BaseModel


class PoolsConfig(BaseModel):
    pool_addresses: List[str]

    @classmethod
    def from_yaml(cls, path: str) -> "PoolsConfig":
        with open(path, "r") as file:
            pools_config = yaml.safe_load(file)
        return cls(**pools_config)

    def get_all_pools(self) -> List[int]:
        return [int(address, 16) for address in self.pool_addresses]
