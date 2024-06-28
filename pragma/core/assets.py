from typing import List, Optional

import yaml
from pydantic import BaseModel

from pragma.core.constants import ALL_ASSETS
from pragma.core.types import DECIMALS, Currency, Pair, UnsupportedAssetError


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

    @staticmethod
    def get_pair_from_asset_configs(
        base_asset: "AssetConfig", quote_asset: "AssetConfig"
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

    @classmethod
    def get_coingecko_id_from_ticker(cls, ticker: str) -> str:
        """
        Return the coingecko id from a ticker.
        Raise UnsupportedAssetError if the ticker is not supported.

        :param ticker: Ticker
        :return: Coingecko id
        """

        asset = try_get_asset_config_from_ticker(ticker)
        return asset.coingecko_id


def try_get_asset_config_from_ticker(ticker: str) -> AssetConfig:
    """
    Return a AssetConfig from a ticker.
    Raise UnsupportedAssetError if the ticker is not supported.

    :param ticker: Ticker
    :return: AssetConfig
    """

    assets = filter(lambda x: x.ticker == ticker, ALL_ASSETS)
    try:
        asset = next(assets)
        return asset
    except StopIteration:
        raise UnsupportedAssetError(f"Asset with ticker {ticker} is not supported.")
