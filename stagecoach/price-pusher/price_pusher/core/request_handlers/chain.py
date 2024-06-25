import logging

from typing import Optional

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.publisher.client import PragmaOnChainClient

from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.utils.assets import asset_to_pair_id

logger = logging.getLogger(__name__)


class ChainRequestHandler(IRequestHandler):
    client: PragmaOnChainClient

    def __init__(self, client: PragmaOnChainClient) -> None:
        self.client = client

    async def fetch_latest_asset_price(self, asset: PragmaAsset) -> Optional[Entry]:
        entry = await self._fetch_oracle_price(asset)
        if entry is None:
            logger.error("Can't get price for {}: unknown asset type.")
            return None
        return entry

    async def _fetch_oracle_price(self, asset: PragmaAsset) -> Optional[Entry]:
        pair_id = asset_to_pair_id(asset)
        oracle_response = None
        try:
            if asset["type"] == "SPOT":
                oracle_response = await self.client.get_spot(pair_id)
                return SpotEntry.from_oracle_response(asset, oracle_response)
            elif asset["type"] == "FUTURE":
                oracle_response = await self.client.get_future(pair_id, 0)
                return FutureEntry.from_oracle_response(asset, oracle_response)
        except Exception as e:
            raise Exception(
                f"Could not fetch fetch price for {asset_to_pair_id(asset)}: {e}"
            )
        if oracle_response is None:
            return None
