import logging

from typing import Optional

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.entry import Entry, FutureEntry, SpotEntry
from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.onchain.client import PragmaOnChainClient

from price_pusher.core.request_handlers.interface import IRequestHandler
from pragma_utils.retries import retry_async

logger = logging.getLogger(__name__)

PRAGMA_ONCHAIN_SOURCE_NAME = "ONCHAIN"
PRAGMA_ONCHAIN_PUBLISHER_NAME = "AGGREGATION"


class ChainRequestHandler(IRequestHandler):
    client: PragmaOnChainClient

    def __init__(self, client: PragmaOnChainClient) -> None:
        self.client = client

    async def fetch_latest_entry(self, data_type: DataTypes, pair: Pair) -> Optional[Entry]:
        entry = await self._fetch_oracle_price(data_type, pair)
        if entry is None:
            logger.error("Can't get price for {}: unknown asset type.")
            return None
        return entry

    async def _fetch_oracle_price(self, data_type: DataTypes, pair: Pair) -> Optional[Entry]:
        pair_id = pair.__repr__()

        async def fetch_action():
            if data_type == "SPOT":
                oracle_response = await self.client.get_spot(pair_id)
                return SpotEntry.from_oracle_response(
                    pair,
                    oracle_response,
                    PRAGMA_ONCHAIN_SOURCE_NAME,
                    PRAGMA_ONCHAIN_PUBLISHER_NAME,
                )
            elif data_type == "FUTURE":
                oracle_response = await self.client.get_future(pair_id, 0)
                return FutureEntry.from_oracle_response(
                    pair,
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
