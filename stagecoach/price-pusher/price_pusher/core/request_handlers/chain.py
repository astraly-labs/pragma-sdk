import logging

from typing import Optional

from pragma.core.assets import PragmaAsset
from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.publisher.client import PragmaOnChainClient

from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.utils.assets import asset_to_pair_id
from price_pusher.utils.retries import retry_async

logger = logging.getLogger(__name__)

PRAGMA_ONCHAIN_SOURCE_NAME = "ONCHAIN"
PRAGMA_ONCHAIN_PUBLISHER_NAME = "AGGREGATION"


class ChainRequestHandler(IRequestHandler):
    client: PragmaOnChainClient

    def __init__(self, client: PragmaOnChainClient) -> None:
        self.client = client

    async def fetch_latest_entry(self, asset: PragmaAsset) -> Optional[Entry]:
        entry = await self._fetch_oracle_price(asset)
        if entry is None:
            logger.error("Can't get price for {}: unknown asset type.")
            return None
        return entry

    async def _fetch_oracle_price(self, asset: PragmaAsset) -> Optional[Entry]:
        pair_id = asset_to_pair_id(asset)

        async def fetch_action():
            if asset["type"] == "SPOT":
                oracle_response = await self.client.get_spot(pair_id)
                return SpotEntry.from_oracle_response(
                    asset,
                    oracle_response,
                    PRAGMA_ONCHAIN_SOURCE_NAME,
                    PRAGMA_ONCHAIN_PUBLISHER_NAME,
                )
            elif asset["type"] == "FUTURE":
                oracle_response = await self.client.get_future(pair_id, 0)
                return FutureEntry.from_oracle_response(
                    asset,
                    oracle_response,
                    PRAGMA_ONCHAIN_SOURCE_NAME,
                    PRAGMA_ONCHAIN_PUBLISHER_NAME,
                )
            return None

        try:
            return await fetch_action()
        except Exception:
            try:
                logger.warning(f"🤔 Fetching price for {pair_id} failed. Retrying...")
                return await retry_async(fetch_action, retries=5, delay_in_s=5)
            except Exception as e:
                raise ValueError(f"Retries for fetching {pair_id} still failed: {e}")
