import logging
import time
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.assets import PragmaAsset
from pragma.core.entry import SpotEntry
from pragma.publisher.types import PublisherFetchError, PublisherInterfaceT

logger = logging.getLogger(__name__)


class AssetQuantities:
    def __init__(self, asset: PragmaAsset, quantities: float):
        self.asset = asset
        self.quantities = quantities


class IndexFetcher(PublisherInterfaceT):
    fetcher: any
    index_name: str
    asset_quantities: List[AssetQuantities]

    def __init__(
        self,
        fetcher: any,
        index_name: str,
        asset_quantities: List[AssetQuantities],
    ):
        self.fetcher = fetcher
        self.index_name = index_name
        self.asset_quantities = asset_quantities

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        spot_entries = []
        for asset_weight in self.asset_quantities:
            spot_entry = await self.fetcher.fetch_pair(asset_weight.asset, session)
            if isinstance(spot_entry, PublisherFetchError):
                return PublisherFetchError(
                    f"Index Computation failed: asset {asset_weight.asset['pair']} not found"
                )
            spot_entries.append(spot_entry)

        index_value = int(
            IndexAggregation(spot_entries, self.asset_quantities).get_index_value()
        )

        return [
            SpotEntry(
                pair_id=self.index_name,
                price=index_value,
                volume=0,
                timestamp=int(time.time()),
                source=self.fetcher.SOURCE,
                publisher=self.fetcher.publisher,
                autoscale_volume=False,
            )
        ]

    def format_url(self, quote_asset, base_asset):
        return self.fetcher.format_url(quote_asset, base_asset)


class IndexAggregation:
    spot_entries: List[SpotEntry]
    asset_quantities: List[AssetQuantities]

    def __init__(
        self, spot_entries: List[SpotEntry], asset_quantities: List[AssetQuantities]
    ):
        self.spot_entries = spot_entries
        self.asset_quantities = asset_quantities

    def get_index_value(self):
        self.standardize_decimals()

        total = sum(
            entry.price * quantities.quantities
            for entry, quantities in zip(self.spot_entries, self.asset_quantities)
        )
        return total

    def standardize_decimals(self):
        decimals = self.asset_quantities[0].asset["decimals"]
        for i, asset_quantity in enumerate(self.asset_quantities):
            asset = asset_quantity.asset
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
