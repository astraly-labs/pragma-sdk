import asyncio
import logging
import time
from typing import List, Union

import requests
from aiohttp import ClientSession

from pragma.core.assets import PRAGMA_ALL_ASSETS, PragmaAsset, PragmaSpotAsset
from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import currency_pair_to_pair_id, str_to_felt
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


import time
from datetime import datetime
from typing import List, Tuple, Union


class AssetWeight:
    def __init__(self, asset: PragmaAsset, weight: float):
        self.asset = asset
        self.weight = weight


class IndexFetcher(PublisherInterfaceT):
    fetcher: any
    index_name: str
    asset_weights: List[AssetWeight]

    def __init__(
        self,
        fetcher: any,
        index_name: str,
        asset_weights: List[AssetWeight],
    ):
        self.fetcher = fetcher
        self.index_name = index_name
        self.asset_weights = asset_weights

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        spot_entries = []
        for asset_weight in self.asset_weights:
            spot_entry = await self.fetcher._fetch_pair(asset_weight.asset, session)
            if isinstance(spot_entry, PublisherFetchError):
                return spot_entry
            spot_entries.append(spot_entry)

        index_value = int(
            IndexAggregation(spot_entries, self.asset_weights).get_index_value()
        )
        return SpotEntry(
            pair_id=self.index_name,
            price=index_value,
            volume=0,
            timestamp=int(time.time()),
            source=self.fetcher.SOURCE,
            publisher=self.fetcher.publisher,
            autoscale_volume=False,
        )

    def format_url(self, quote_asset, base_asset):
        return None


class IndexAggregation:
    spot_entries: List[SpotEntry]
    asset_weights: List[AssetWeight]

    def __init__(self, spot_entries: List[SpotEntry], asset_weights: List[AssetWeight]):
        self.spot_entries = spot_entries
        self.asset_weights = asset_weights

    def get_index_value(self):
        self.standardize_decimals()
        total = sum(
            entry.price * weight.weight
            for entry, weight in zip(self.spot_entries, self.asset_weights)
        )
        total_weight = sum(weight.weight for weight in self.asset_weights)
        return total / total_weight

    def standardize_decimals(self):
        decimals = self.asset_weights[0].asset["decimals"]
        for asset_weight in self.asset_weights:
            asset = asset_weight.asset
            if asset["decimals"] > decimals:
                exponent = asset["decimals"] - decimals
                for entry in self.spot_entries:
                    entry.price *= 10**exponent
                    entry.volume *= 10**exponent
                decimals = asset["decimals"]

