import logging
from typing import Optional

from pragma.common.types import DataTypes
from pragma.common.types.pair import Pair
from pragma.common.types.entry import Entry, SpotEntry
from pragma.offchain.client import PragmaAPIClient, EntryResult
from pragma.common.types import AggregationMode
from pragma.offchain.types import Interval

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
        entry_result: EntryResult = await self.client.get_entry(
            pair=pair.__repr__(), interval=Interval.ONE_MINUTE, aggregation=AggregationMode.MEDIAN
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
