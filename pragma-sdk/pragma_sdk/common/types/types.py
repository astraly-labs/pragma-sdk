from enum import StrEnum, unique
from typing import Optional, Dict

from pydantic import model_validator
from pydantic.dataclasses import dataclass
from starknet_py.net.client_models import ResourceBounds


Address = int
HexStr = str
Decimals = int
UnixTimestamp = int


@unique
class Environment(StrEnum):
    DEV = "dev"
    PROD = "prod"


@unique
class AggregationMode(StrEnum):
    MEDIAN = "Median"
    AVERAGE = "Mean"
    ERROR = "Error"

    def serialize(self) -> Dict[str, None]:
        return {self.value: None}


@unique
class DataTypes(StrEnum):
    SPOT = "Spot"
    FUTURE = "Future"

    def __repr__(self):
        return f"'{self.value}'"


@dataclass(frozen=True)
class ExecutionConfig:
    pagination: int = 40
    max_fee: int = int(1e18)
    enable_strk_fees: bool = False
    l1_resource_bounds: Optional[ResourceBounds] = None
    auto_estimate: bool = False

    @model_validator(mode="after")  # type: ignore[misc]
    def post_root(self) -> None:
        if self.auto_estimate == (self.l1_resource_bounds is not None):
            raise ValueError("Either auto_estimate or l1_resource_bounds must be set")
