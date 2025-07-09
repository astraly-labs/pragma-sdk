import logging

from typing import List

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

    async def fetch_latest_entries(
        self,
        pair: Pair,
        data_type: DataTypes,
        sources: List[str],
    ) -> List[Entry]:
        entry = await self._fetch_oracle_price(pair, data_type, sources)
        if entry is None:
            logger.error("Can't get price for {}: unknown asset type.")
            return None
        return entry

    async def _fetch_oracle_price(
        self, pair: Pair, data_type: DataTypes, sources: List[str]
    ) -> List[Entry]:
        pair_id = str(pair)

        async def fetch_action() -> List[Entry]:
            entries = []
            new_entry = None
            match data_type:
                case DataTypes.SPOT:
                    oracle_response = await self.client.get_spot(
                        pair_id, sources=sources, block_id="pending"
                    )
                    new_entry = SpotEntry.from_oracle_response(
                        pair,
                        oracle_response,
                        PRAGMA_ONCHAIN_SOURCE_NAME,
                        PRAGMA_ONCHAIN_PUBLISHER_NAME,
                    )
                case DataTypes.FUTURE:
                    # TODO: We only fetch the perp entry for now
                    oracle_response = await self.client.get_future(
                        pair_id, 0, sources=sources, block_id="pending"
                    )
                    new_entry = FutureEntry.from_oracle_response(
                        pair,
                        oracle_response,
                        PRAGMA_ONCHAIN_SOURCE_NAME,
                        PRAGMA_ONCHAIN_PUBLISHER_NAME,
                    )
            if new_entry is not None:
                entries.append(new_entry)
            return entries

        try:
            return await fetch_action()
        except Exception:
            try:
                logger.warning(f"🤔 Fetching price for {pair_id} failed. Retrying...")
                return await retry_async(
                    fetch_action, retries=5, delay_in_s=5, logger=logger
                )
            except Exception as e:
                raise ValueError(f"Retries for fetching {pair_id} still failed: {e}")
