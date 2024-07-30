import logging
from typing import List

from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import Entry, FutureEntry, SpotEntry
from pragma_sdk.offchain.client import PragmaAPIClient, EntryResult
from pragma_sdk.common.types.types import AggregationMode
from pragma_sdk.offchain.types import Interval

from price_pusher.core.request_handlers.interface import IRequestHandler

logger = logging.getLogger(__name__)

PRAGMA_API_SOURCE_NAME = "PragmaAPI"
PRAGMA_API_PUBLISHER_NAME = "AGGREGATION"


class APIRequestHandler(IRequestHandler):
    client: PragmaAPIClient

    def __init__(self, client: PragmaAPIClient) -> None:
        self.client = client

    async def fetch_latest_entries(self, data_type: DataTypes, pair: Pair) -> List[Entry]:
        """
        Fetch last entry for the asset from the API.
        """
        if data_type is DataTypes.FUTURE:
            return await self._fetch_latest_future_entries(pair)
        else:
            return await self._fetch_latest_spot_entry(pair)

    async def _fetch_latest_spot_entry(self, pair: Pair) -> List[Entry]:
        """
        Fetch the latest spot entry for the given pair.
        """
        entry_result: EntryResult = await self.client.get_entry(
            pair=str(pair),
            interval=Interval.ONE_MINUTE,
            aggregation=AggregationMode.MEDIAN,
        )
        if entry_result is None:
            return []
        entry = SpotEntry(
            pair_id=entry_result.pair_id,
            price=int(entry_result.data, 16),
            # PragmaAPI returns timestamp in millis, we convert to s
            timestamp=entry_result.timestamp / 1000,
            source=PRAGMA_API_SOURCE_NAME,
            publisher=PRAGMA_API_PUBLISHER_NAME,
        )
        return [entry]

    async def _fetch_latest_future_entries(self, pair: Pair) -> List[Entry]:
        """
        For a given pair, fetch the latest perp price and the last future price for each
        expiries.
        """
        entries = []
        if last_perp := await self._fetch_latest_perp(pair):
            entries.append(last_perp)
        if last_futures := await self._fetch_latest_futures(pair):
            entries.extend(last_futures)
        return entries

    async def _fetch_latest_perp(self, pair: Pair) -> List[Entry]:
        """
        For a given pair, fetch the latest perp entry from the Pragma API.
        """
        entry_result = await self.client.get_future_entry(
            pair=str(pair),
            interval=Interval.ONE_MINUTE,
            aggregation=AggregationMode.MEDIAN,
        )
        if entry_result is None:
            return []

        entry = FutureEntry(
            pair_id=entry_result.pair_id,
            price=int(entry_result.data, 16),
            # PragmaAPI returns timestamp in millis, we convert to s
            timestamp=entry_result.timestamp / 1000,
            source=PRAGMA_API_SOURCE_NAME,
            publisher=PRAGMA_API_PUBLISHER_NAME,
            expiry_timestamp=entry_result.expiry,
        )
        return entry

    async def _fetch_latest_futures(self, pair: Pair) -> List[Entry]:
        """
        For a given pair, fetch all the available expiries and the last price
        available.
        """
        future_entries = []
        expiries = await self.client.get_expiries_list(pair)
        for expiry in expiries:
            entry_result = await self.client.get_future_entry(
                pair=str(pair),
                interval=Interval.ONE_MINUTE,
                aggregation=AggregationMode.MEDIAN,
                expiry=expiry,
            )
            if entry_result is None:
                continue
            future_entries.append(
                FutureEntry(
                    pair_id=entry_result.pair_id,
                    price=int(entry_result.data, 16),
                    # PragmaAPI returns timestamp in millis, we convert to s
                    timestamp=entry_result.timestamp / 1000,
                    source=PRAGMA_API_SOURCE_NAME,
                    publisher=PRAGMA_API_PUBLISHER_NAME,
                    expiry_timestamp=entry_result.expiry,
                )
            )
        return future_entries
