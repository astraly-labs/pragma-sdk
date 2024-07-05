import logging
from typing import Optional

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

    async def fetch_latest_entry(self, data_type: DataTypes, pair: Pair) -> Optional[Entry]:
        """
        Fetch last entry for the asset from the API.
        TODO: Currently only works for spot assets.
        """
        if data_type is DataTypes.FUTURE:
            entry_result: EntryResult = await self.client.get_future_entry(
                pair=pair.__repr__(),
                interval=Interval.ONE_MINUTE,
                aggregation=AggregationMode.MEDIAN,
            )

            entry = FutureEntry(
                pair_id=entry_result.pair_id,
                price=int(entry_result.data, 16),
                # PragmaAPI returns timestamp in millis, we convert to s
                timestamp=entry_result.timestamp / 1000,
                source=PRAGMA_API_SOURCE_NAME,
                publisher=PRAGMA_API_PUBLISHER_NAME,
                expiry_timestamp=entry_result.expiry
            )
        else:
            entry_result: EntryResult = await self.client.get_entry(
                pair=pair.__repr__(),
                interval=Interval.ONE_MINUTE,
                aggregation=AggregationMode.MEDIAN,
            )
            entry = SpotEntry(
                pair_id=entry_result.pair_id,
                price=int(entry_result.data, 16),
                # PragmaAPI returns timestamp in millis, we convert to s
                timestamp=entry_result.timestamp / 1000,
                source=PRAGMA_API_SOURCE_NAME,
                publisher=PRAGMA_API_PUBLISHER_NAME,
            )
        return entry
