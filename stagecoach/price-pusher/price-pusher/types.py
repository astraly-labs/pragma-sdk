from pragma.core.assets import PragmaSpotAsset, PragmaFutureAsset, get_asset_spec_for_pair_id_by_type
from typing import List, Optional
from typing_extensions import Annotated
from enum import Enum

from pydantic import BaseModel, field_validator, RootModel, Field, ConfigDict

class PriceConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pairs_spot: Optional[List[PragmaSpotAsset]] = None
    pairs_future: Optional[List[PragmaFutureAsset]] = None
    time_difference: Annotated[int, Field(strict=True, gt=0)] 
    price_deviation: Annotated[float, Field(strict=True, gt=0)]

    @field_validator('pairs_spot', mode="before")
    def validate_pairs_spot(cls, value):
        assets: List[PragmaSpotAsset] = []
        for pair in value:
            pair = pair.replace(' ', '').upper()
            splitted = pair.split('/')
            if len(splitted) != 2:
                return ValueError("Pair should be formatted as X/Y")
            
            asset = get_asset_spec_for_pair_id_by_type(pair, "SPOT")
            assets.append(asset)

        return assets
    
    @field_validator('pairs_future', mode="before")
    def validate_pairs_future(cls, value):
        assets: List[PragmaFutureAsset] = []
        for pair in value:
            pair = pair.replace(' ', '').upper()
            splitted = pair.split('/')
            if len(splitted) != 2:
                return ValueError("Pair should be formatted as X/Y")
            
            asset = get_asset_spec_for_pair_id_by_type(pair, "FUTURE")
            assets.append(asset)

        return assets


class PriceConfigFile(RootModel):
    root: List[PriceConfig]


class Envirronment(Enum):
    DEV = 1
    PROD = 2

class DataSource(Enum):
    ONCHAIN = 1
    OFFCHAIN = 2
    DEFILLAMA = 3