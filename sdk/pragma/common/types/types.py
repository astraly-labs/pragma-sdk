from enum import StrEnum, unique
from dataclasses import dataclass
from typing import Optional

from starknet_py.net.client_models import ResourceBounds


ADDRESS = int
HEX_STR = str
DECIMALS = int
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

    def serialize(self):
        return {self.value: None}


@unique
class DataTypes(StrEnum):
    SPOT = "Spot"
    FUTURE = "Future"


@dataclass(frozen=True)
class ExecutionConfig:
    pagination: Optional[int] = 40
    max_fee: Optional[int] = int(1e18)
    enable_strk_fees: Optional[bool] = False
    l1_resource_bounds: Optional[ResourceBounds] = None
    auto_estimate: Optional[bool] = False
