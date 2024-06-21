from typing import List, Optional

import yaml
from pragma.core.assets import (
    PragmaFutureAsset,
    PragmaSpotAsset,
    get_asset_spec_for_pair_id_by_type,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Annotated


class PriceConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pairs_spot: Optional[List[PragmaSpotAsset]] = None
    pairs_future: Optional[List[PragmaFutureAsset]] = None
    time_difference: Annotated[int, Field(strict=True, gt=0)]
    price_deviation: Annotated[float, Field(strict=True, gt=0)]

    @field_validator("pairs_spot", mode="before")
    def validate_pairs_spot(cls, value: List[str]) -> List[PragmaSpotAsset]:
        assets: List[PragmaSpotAsset] = []
        for pair in value:
            pair = pair.replace(" ", "").upper()
            splitted = pair.split("/")
            if len(splitted) != 2:
                return ValueError("Pair should be formatted as X/Y")

            asset = get_asset_spec_for_pair_id_by_type(pair, "SPOT")
            assets.append(asset)

        return assets

    @field_validator("pairs_future", mode="before")
    def validate_pairs_future(cls, value: List[str]) -> List[PragmaFutureAsset]:
        assets: List[PragmaFutureAsset] = []
        for pair in value:
            pair = pair.replace(" ", "").upper()
            splitted = pair.split("/")
            if len(splitted) != 2:
                return ValueError("Pair should be formatted as X/Y")

            asset = get_asset_spec_for_pair_id_by_type(pair, "FUTURE")
            assets.append(asset)

        return assets

    @classmethod
    def from_yaml(cls, path: str) -> List["PriceConfig"]:
        with open(path, "r") as file:
            price_configs = yaml.safe_load(file)
        return [cls(**config) for config in price_configs]
