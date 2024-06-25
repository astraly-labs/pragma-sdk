import logging

from typing import Optional

from pragma.core.assets import PragmaAsset, PragmaFutureAsset, PragmaSpotAsset
from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.publisher.client import PragmaOnChainClient
from pragma.core.mixins.oracle import OracleResponse

from price_pusher.core.request_handlers.interface import IRequestHandler

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
        pair_id = list(asset.pair).join("/")

        oracle_response: Optional[OracleResponse] = None
        if isinstance(asset, PragmaSpotAsset):
            oracle_response = await self.client.get_spot(pair_id)
            return SpotEntry.from_dict(oracle_response)
        elif isinstance(asset, PragmaFutureAsset):
            oracle_response = await self.client.get_future(pair_id, 0)
            return FutureEntry.from_dict(oracle_response)
        if oracle_response is None:
            return None
