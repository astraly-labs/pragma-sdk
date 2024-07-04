from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Annotated

from pragma.common.configs.asset_config import (
    try_get_asset_config_from_ticker,
    AssetConfig,
)
from pragma.common.types import DataTypes, Pair


class PairConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    spot: Optional[List[Pair]] = None
    future: Optional[List[Pair]] = None


class PriceConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pairs: PairConfig
    time_difference: Annotated[int, Field(strict=True, gt=0)]
    price_deviation: Annotated[float, Field(strict=True, gt=0)]

    @field_validator("pairs", mode="before")
    def validate_pairs(cls, value: PairConfig) -> PairConfig:
        if "spot" in value:
            value["spot"] = cls.validate_asset_pairs(value["spot"])
        if "future" in value:
            value["future"] = cls.validate_asset_pairs(value["future"])
        return value

    @staticmethod
    def validate_asset_pairs(pairs: List[str]) -> List:
        assets = []
        for pair in pairs:
            pair = pair.replace(" ", "").upper()
            splitted = pair.split("/")
            if len(splitted) != 2:
                raise ValueError("Pair should be formatted as 'BASE/QUOTE'")
            base_currency = try_get_asset_config_from_ticker(splitted[0])
            quote_currency = try_get_asset_config_from_ticker(splitted[1])
            assets.append(
                AssetConfig.get_pair_from_asset_configs(base_currency, quote_currency)
            )
        return assets

    @classmethod
    def from_yaml(cls, path: str) -> List["PriceConfig"]:
        with open(path, "r") as file:
            price_configs = yaml.safe_load(file)
        list_configs = [cls(**config) for config in price_configs]
        # TODO: verify that pairs are unique among groups
        return list_configs

    def get_unique_spot_pairs(self) -> List[Pair]:
        """
        Get unique spot pairs from the configuration.

        Returns:
            List of unique Pairs.
        """
        if self.pairs.spot is None:
            return []
        unique_spot_assets = []
        for spot_asset in self.pairs.spot:
            if spot_asset not in unique_spot_assets:
                unique_spot_assets.append(spot_asset)
        return list(unique_spot_assets)

    def get_unique_future_pairs(self) -> List[Pair]:
        """
        Get unique future assets from the configuration.

        Returns:
            List of unique PragmaFutureAssets.
        """
        if self.pairs.future is None:
            return []
        unique_future_assets = []
        for future_asset in self.pairs.future:
            if future_asset not in unique_future_assets:
                unique_future_assets.append(future_asset)
        return list(unique_future_assets)

    def get_all_assets(self) -> Dict[DataTypes, List[Pair]]:
        """
        Get all spot and future assets from the configuration.

        Returns:
            Dict from DataTypes to List of Pairs.
        """
        pair_dict_by_type = {}
        pair_dict_by_type[DataTypes.SPOT] = self.get_unique_spot_pairs()
        pair_dict_by_type[DataTypes.FUTURE] = self.get_unique_future_pairs()
        return pair_dict_by_type


def get_unique_spot_pairs_from_config_list(
    price_configs: List[PriceConfig],
) -> List[Pair]:
    """
    Extract unique spot assets from a list of PriceConfig objects.

    Args:
        price_configs: List of PriceConfig objects.

    Returns:
        List of unique Pairs.
    """
    unique_spot_assets: List[Pair] = []
    for config in price_configs:
        for asset in config.get_unique_spot_pairs():
            if asset not in unique_spot_assets:
                unique_spot_assets.append(asset)
    return unique_spot_assets


def get_unique_future_pairs_from_config_list(
    price_configs: List[PriceConfig],
) -> List[Pair]:
    """
    Extract unique future assets from a list of PriceConfig objects.

    Args:
        price_configs: List of PriceConfig objects.

    Returns:
        List of unique Pairs.
    """
    unique_future_assets: List[Pair] = []
    for config in price_configs:
        for asset in config.get_unique_future_pairs():
            if asset not in unique_future_assets:
                unique_future_assets.append(asset)
    return unique_future_assets
