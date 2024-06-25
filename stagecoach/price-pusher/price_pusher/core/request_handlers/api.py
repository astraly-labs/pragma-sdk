import logging
from typing import Optional

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry, SpotEntry
from pragma.publisher.client import PragmaAPIClient, EntryResult, PragmaAPIError

from price_pusher.core.request_handlers.interface import IRequestHandler

logger = logging.getLogger(__name__)


class APIRequestHandler(IRequestHandler):
    client: PragmaAPIClient

    def __init__(self, client: PragmaAPIClient) -> None:
        self.client = client

    async def fetch_latest_asset_price(self, asset: PragmaAsset) -> Optional[Entry]:
        """
        Fetch last entry for the asset.
        TODO: does not work for future.
        """
        pair = list(asset.pair).join("/")
        try:
            entry_result: EntryResult = await self.client.get_entry(pair)
        except PragmaAPIError:
            entry_result = None

        if entry_result is None:
            logger.error("Can't get price for {}: unknown asset type.")
            return None

        entry = SpotEntry(
            pair_id=entry_result.pair_id,
            price=int(entry_result.data, 16),
            timestamp=entry_result.timestamp,
            source="PragmaAPI",
            publisher="AGGREGATION",
        )
        return entry
