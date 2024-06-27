from typing import List, Optional

import yaml
from pragma.core.assets import (
    PragmaFutureAsset,
    PragmaAsset,
    PragmaSpotAsset,
    AssetType,
    get_asset_spec_for_pair_id_by_type,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Annotated


class PairConfig(BaseModel):
    spot: Optional[List[PragmaSpotAsset]] = None
    future: Optional[List[PragmaFutureAsset]] = None


class PriceConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pairs: PairConfig
    time_difference: Annotated[int, Field(strict=True, gt=0)]
    price_deviation: Annotated[float, Field(strict=True, gt=0)]

    @field_validator("pairs", mode="before")
    def validate_pairs(cls, value: PairConfig) -> PairConfig:
        if "spot" in value:
            value["spot"] = cls.validate_asset_pairs(value["spot"], "SPOT")
        if "future" in value:
            value["future"] = cls.validate_asset_pairs(value["future"], "FUTURE")
        return value

    @staticmethod
    def validate_asset_pairs(pairs: List[str], asset_type: AssetType) -> List:
        assets = []
        for pair in pairs:
            pair = pair.replace(" ", "").upper()
            splitted = pair.split("/")
            if len(splitted) != 2:
                raise ValueError("Pair should be formatted as 'BASE/QUOTE'")
            asset = get_asset_spec_for_pair_id_by_type(pair, asset_type)
            assets.append(asset)
        return assets

    @classmethod
    def from_yaml(cls, path: str) -> List["PriceConfig"]:
        with open(path, "r") as file:
            price_configs = yaml.safe_load(file)
        list_configs = [cls(**config) for config in price_configs]
        # TODO: verify that pairs are unique among groups
        return list_configs

    def get_unique_spot_assets(self) -> List[PragmaSpotAsset]:
        """
        Get unique spot assets from the configuration.

        Returns:
            List of unique PragmaSpotAssets.
        """
        return list(dict.fromkeys(self.pairs.spot).keys()) if self.pairs.spot else []

    def get_unique_future_assets(self) -> List[PragmaFutureAsset]:
        """
        Get unique future assets from the configuration.

        Returns:
            List of unique PragmaFutureAssets.
        """
        return list(dict.fromkeys(self.pairs.future).keys()) if self.pairs.spot else []

    def get_all_assets(self) -> List[PragmaAsset]:
        """
        Get all spot and future assets from the configuration.

        Returns:
            List[PragmaAsset]
        """
        spot_assets = self.get_unique_spot_assets()
        future_assets = self.get_unique_future_assets()
        return spot_assets + future_assets


def get_unique_spot_assets_from_config_list(
    price_configs: List[PriceConfig],
) -> List[PragmaSpotAsset]:
    """
    Extract unique spot assets from a list of PriceConfig objects.

    Args:
        price_configs: List of PriceConfig objects.

    Returns:
        List of unique PragmaSpotAssets.
    """
    unique_spot_assets: List[PragmaSpotAsset] = []
    for config in price_configs:
        for asset in config.get_unique_spot_assets():
            if asset not in unique_spot_assets:
                unique_spot_assets.append(asset)
    return unique_spot_assets


def get_unique_future_assets_from_config_list(
    price_configs: List[PriceConfig],
) -> List[PragmaFutureAsset]:
    """
    Extract unique future assets from a list of PriceConfig objects.

    Args:
        price_configs: List of PriceConfig objects.

    Returns:
        List of unique PragmaFutureAssets.
    """
    unique_future_assets: List[PragmaFutureAsset] = []
    for config in price_configs:
        for asset in config.get_unique_future_assets():
            if asset not in unique_future_assets:
                unique_future_assets.append(asset)
    return unique_future_assets
