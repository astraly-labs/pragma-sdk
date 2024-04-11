import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset
from pragma.core.entry import SpotEntry
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)



class AssetWeight:
    def __init__(self, asset: PragmaAsset, weight: float):
        self.asset = asset
        self.weight = weight

    def __repr__(self):
        return f"Asset: {self.asset}, Weight: {self.weight}"


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
                return PublisherFetchError(
                    f"Index Computation failed: asset {asset_weight.asset['pair']} not found"
                )
            spot_entries.append(spot_entry)

        index_value = int(
            IndexAggregation(spot_entries, self.asset_weights).get_index_value()
        )

        return [SpotEntry(
            pair_id=self.index_name,
            price=index_value,
            volume=0,
            timestamp=int(time.time()),
            source=self.fetcher.SOURCE,
            publisher=self.fetcher.publisher,
            autoscale_volume=False,
        )]

    def format_url(self, quote_asset, base_asset):
        return self.fetcher.format_url(quote_asset, base_asset)


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
        for i in range(0, len(self.asset_weights)):
            asset = self.asset_weights[i].asset
            exponent = abs(asset["decimals"] - decimals)
            if asset["decimals"] > decimals:
                for j in range(0, i):
                    self.spot_entries[j].price *= 10**exponent
                    self.spot_entries[j].volume *= 10**exponent
            elif asset["decimals"] < decimals:
                self.spot_entries[i].price *= 10**exponent
                self.spot_entries[i].volume *= 10**exponent
            else:
                continue

            decimals = asset["decimals"]
