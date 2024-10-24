import yaml

from typing import Dict, List

from pydantic import BaseModel
from typing_extensions import Annotated


class PoolsConfig(BaseModel):
    lp_addresses: List[int]

    @classmethod
    def from_yaml(cls, path: str) -> List["PoolsConfig"]:
        with open(path, "r") as file:
            pools_config = yaml.safe_load(file)
        return pools_config

    def get_all_pools(self) -> List[int]:
        return self.lp_addresses
