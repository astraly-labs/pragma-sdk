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

    async def fetch_latest_entries(self, data_type: DataTypes, pair: Pair) -> List[Entry]:
        entry = await self._fetch_oracle_price(data_type, pair)
        if entry is None:
            logger.error("Can't get price for {}: unknown asset type.")
            return None
        return entry

    async def _fetch_oracle_price(self, data_type: DataTypes, pair: Pair) -> List[Entry]:
        pair_id = str(pair)

        async def fetch_action() -> List[Entry]:
            entries = []
            match data_type:
                case DataTypes.SPOT:
                    oracle_response = await self.client.get_spot(pair_id, block_id="pending")
                    entry = SpotEntry.from_oracle_response(
                        pair,
                        oracle_response,
                        PRAGMA_ONCHAIN_SOURCE_NAME,
                        PRAGMA_ONCHAIN_PUBLISHER_NAME,
                    )
                    if entry is not None:
                        entries.append(entry)
                case DataTypes.FUTURE:
                    # TODO: We only fetch the perp entry for now
                    oracle_response = await self.client.get_future(pair_id, 0, block_id="pending")
                    entries.append(
                        FutureEntry.from_oracle_response(
                            pair,
                            oracle_response,
                            PRAGMA_ONCHAIN_SOURCE_NAME,
                            PRAGMA_ONCHAIN_PUBLISHER_NAME,
                        )
                    )
                case _:
                    logger.error(f"POLLER found unknown asset type: {data_type}")
            return entries

        try:
            return await fetch_action()
        except Exception as e:
            logger.error(f"Failed: {e}")
            try:
                logger.warning(f"🤔 Fetching price for {pair_id} failed. Retrying...")
                return await retry_async(fetch_action, retries=5, delay_in_s=5, logger=logger)
            except Exception as e:
                raise ValueError(f"Retries for fetching {pair_id} still failed: {e}")
