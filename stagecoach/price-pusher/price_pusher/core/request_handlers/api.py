import logging
from typing import Optional

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry, SpotEntry
from pragma.publisher.client import PragmaAPIClient, EntryResult

from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.utils.assets import asset_to_pair_id

logger = logging.getLogger(__name__)

PRAGMA_API_SOURCE_NAME = "PragmaAPI"
PRAGMA_API_PUBLISHER_NAME = "AGGREGATION"


class APIRequestHandler(IRequestHandler):
    client: PragmaAPIClient

    def __init__(self, client: PragmaAPIClient) -> None:
        self.client = client

    async def fetch_latest_entry(self, asset: PragmaAsset) -> Optional[Entry]:
        """
        Fetch last entry for the asset from the API.
        TODO: Currently only works for spot assets.
        """
        pair = asset_to_pair_id(asset)
        entry_result: EntryResult = await self.client.get_entry(pair)
        entry = SpotEntry(
            pair_id=entry_result.pair_id,
            price=int(entry_result.data, 16),
            # PragmaAPI returns timestamp in millis, we convert to s
            timestamp=entry_result.timestamp / 1000,
            source=PRAGMA_API_SOURCE_NAME,
            publisher=PRAGMA_API_PUBLISHER_NAME,
        )
        return entry
