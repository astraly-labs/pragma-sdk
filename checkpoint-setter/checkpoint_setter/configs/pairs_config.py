from typing import List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from pragma_sdk.common.configs.asset_config import (
    AssetConfig,
)
from pragma_sdk.common.types.pair import Pair


class PairsConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    spot: Optional[List[Pair]] = None
    future: Optional[List[Pair]] = None

    @field_validator("spot", mode="before")
    def validate_spot(cls, value: Optional[List[str]]) -> Optional[List[Pair]]:
        return cls.validate_pairs(value)

    @field_validator("future", mode="before")
    def validate_future(cls, value: Optional[List[str]]) -> Optional[List[Pair]]:
        return cls.validate_pairs(value)

    @staticmethod
    def validate_pairs(raw_pairs: Optional[List[str]]) -> List:
        pairs: List[Pair] = []
        if raw_pairs is None:
            return pairs
        for raw_pair in raw_pairs:
            raw_pair = raw_pair.replace(" ", "").upper()
            splitted = raw_pair.split("/")
            if len(splitted) != 2:
                raise ValueError("Pair should be formatted as 'BASE/QUOTE'")
            base_currency = AssetConfig.from_ticker(splitted[0])
            quote_currency = AssetConfig.from_ticker(splitted[1])
            pair = Pair.from_asset_configs(base_currency, quote_currency)
            if pair is None:
                raise ValueError("⛔ Could not create pair for {base_currency}/{quote_currency}")
            pairs.append(pair)
        return list(set(pairs))

    @classmethod
    def from_yaml(cls, path: str) -> "PairsConfig":
        with open(path, "r") as file:
            pairs_config = yaml.safe_load(file)
        config = cls(**pairs_config)

        spot_empty = config.spot is None or len(config.spot) == 0
        future_empty = config.future is None or len(config.future) == 0

        if spot_empty and future_empty:
            raise ValueError(
                "⛔ No pair found: you need to specify at least one "
                "spot/future pair in the configuration file."
            )
        return config
