from typing import List, Optional

import yaml
from pydantic import BaseModel

from pragma.core.types import DECIMALS, Currency, Pair
from pragma.core.utils import currency_pair_to_pair_id


class AssetConfig(BaseModel):
    name: str
    decimals: DECIMALS
    ticker: str
    coingecko_id: Optional[str] = None
    abstract: Optional[bool] = False

    @classmethod
    def from_yaml(cls, path: str) -> List["AssetConfig"]:
        with open(path, "r") as file:
            assets_configs = yaml.safe_load(file)
        list_configs = [cls(**config) for config in assets_configs]
        # TODO: verify that assets are unique
        return list_configs

    def get_currency(self):
        """
        Return a Currency object from the AssetConfig.
        """

        return Currency(
            id_=self.ticker,
            decimals=self.decimals,
            is_abstract_currency=self.abstract,
        )


def get_pair_from_asset_configs(
    base_asset: AssetConfig, quote_asset: AssetConfig
) -> Pair:
    """
    Return a Pair from two AssetConfigs.

    :param base_asset: Base asset
    :param quote_asset: Quote asset
    :return: Pair
    """

    return Pair(
        base_currency=base_asset.get_currency(),
        quote_currency=quote_asset.get_currency(),
    )
