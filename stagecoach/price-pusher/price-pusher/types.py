from pragma.core.types import Pair
from typing import List
from enum import Enum

from pydantic import BaseModel, conint, confloat, field_validator, RootModel

class PriceConfig(BaseModel):
    pairs: str
    time_difference: conint(gt=0)  # time_difference must be a positive integer
    price_deviation: confloat(gt=0)  # price_deviation must be a positive float

    @field_validator('pairs')
    def validate_pairs(cls, value):
        pairs = value.split(',')
        for pair in pairs:
            if not pair:
                raise ValueError('Empty pair found in pairs string')
            if ' ' in pair:
                raise ValueError('Pairs string must not contain spaces')
            if len(pair.split('/')) != 2:
                raise ValueError('Each pair must be in the format base/quote')
        return value


class PriceConfigFile(RootModel):
    root: List[PriceConfig]


class Envirronment(Enum):
    DEV = 1
    PROD = 2

class DataSource(Enum):
    ONCHAIN = 1
    OFFCHAIN = 2
    DEFILLAMA = 3