import logging
import time
from typing import Any, List, Union

from aiohttp import ClientSession

from pragma.core.entry import SpotEntry
from pragma.core.types import Pair
from pragma.publisher.types import PublisherFetchError, FetcherInterfaceT

logger = logging.getLogger(__name__)


class AssetQuantities:
    def __init__(self, pair: Pair, quantities: float):
        self.pair = pair
        self.quantities = quantities


# TODO(#000): rewrite this class
class IndexFetcher(FetcherInterfaceT):
    fetcher: Any
    index_name: str
    pair_quantities: List[AssetQuantities]

    def __init__(
        self,
        fetcher: Any,
        index_name: str,
        pair_quantities: List[AssetQuantities],
    ):
        self.fetcher = fetcher
        self.index_name = index_name
        self.pair_quantities = pair_quantities

    async def fetch(
        self, session: ClientSession
    ) -> List[Union[SpotEntry, PublisherFetchError]]:
        spot_entries = []
        for pair_weight in self.pair_quantities:
            spot_entry = await self.fetcher.fetch_pair(pair_weight.pair, session)
            if isinstance(spot_entry, PublisherFetchError):
                return PublisherFetchError(
                    f"Index Computation failed: pair {pair_weight.pair['pair']} not found"
                )
            spot_entries.append(spot_entry)

        index_value = int(
            IndexAggregation(spot_entries, self.pair_quantities).get_index_value()
        )

        return [
            SpotEntry(
                pair_id=self.index_name,
                price=index_value,
                volume=0,
                timestamp=int(time.time()),
                source=self.fetcher.SOURCE,
                publisher=self.fetcher.publisher,
            )
        ]

    def format_url(self, quote_pair, base_pair):
        return self.fetcher.format_url(quote_pair, base_pair)


class IndexAggregation:
    spot_entries: List[SpotEntry]
    pair_quantities: List[AssetQuantities]

    def __init__(
        self, spot_entries: List[SpotEntry], pair_quantities: List[AssetQuantities]
    ):
        self.spot_entries = spot_entries
        self.pair_quantities = pair_quantities

    def get_index_value(self):
        self.standardize_decimals()

        total = sum(
            entry.price * quantities.quantities
            for entry, quantities in zip(self.spot_entries, self.pair_quantities)
        )
        return total

    def standardize_decimals(self):
        decimals = self.pair_quantities[0].pair.decimals()
        for i, pair_quantity in enumerate(self.pair_quantities):
            pair = pair_quantity.pair
            exponent = abs(pair.decimals() - decimals)
            if pair.decimals() > decimals:
                for j in range(0, i):
                    self.spot_entries[j].price *= 10**exponent
                    self.spot_entries[j].volume *= 10**exponent
            elif pair.decimals() < decimals:
                self.spot_entries[i].price *= 10**exponent
                self.spot_entries[i].volume *= 10**exponent
            else:
                continue

            decimals = pair.decimals()
