import asyncio
import logging
import statistics
import time

from typing import List, Optional

from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.types import DataTypes
from pragma_sdk.common.utils import publisher_to_felt, str_to_felt
from pragma_sdk.onchain.client import PragmaOnChainClient

from price_pusher.core.request_handlers.interface import IRequestHandler

logger = logging.getLogger(__name__)

OWN_ENTRIES_SOURCE_NAME = "OWN_ENTRIES"
ALLOWED_SOURCES_TTL_S = 600
NO_ENTRY_ERROR = "No data entry found"


class PublisherRequestHandler(IRequestHandler):
    """
    Reads this publisher's own on-chain entries instead of the aggregated median.

    The aggregated timestamp is the max across every publisher, so it stays
    fresh as long as someone else publishes: a publisher that shares its feeds
    (a validator next to Pragma's publishers) would then never push. This
    handler returns one entry per pair: the median of the publisher's own
    prices, stamped with its oldest source timestamp, a whitelisted source it
    never published counting as 0. Any stale or missing source triggers a push.
    """

    def __init__(self, client: PragmaOnChainClient, publisher: str | int) -> None:
        self.client = client
        self.publisher = publisher_to_felt(publisher)
        self._allowed_sources: Optional[set[int]] = None
        self._allowed_sources_at = 0.0

    async def fetch_latest_entries(
        self,
        pair: Pair,
        data_type: DataTypes,
        sources: Optional[List[str]] = None,
    ) -> List[Entry]:
        if data_type != DataTypes.SPOT:
            logger.warning(f"Own entries are only tracked for spot pairs, not {pair}")
            return []

        allowed = await self._get_allowed_sources()
        sources = [
            source
            for source in sources or []
            if allowed is None or str_to_felt(source) in allowed
        ]
        if not sources:
            return []

        own_entries = await asyncio.gather(
            *(self._get_own_entry(pair, source) for source in sources)
        )
        found = [entry for entry in own_entries if entry is not None]
        if not found:
            return []

        oldest = (
            0
            if len(found) < len(sources)
            else min(entry.get_timestamp() for entry in found)
        )
        return [
            SpotEntry(
                pair_id=pair.id,
                price=int(statistics.median(entry.price for entry in found)),
                timestamp=oldest,
                source=OWN_ENTRIES_SOURCE_NAME,
                publisher=self.publisher,
            )
        ]

    async def _get_own_entry(self, pair: Pair, source: str) -> Optional[SpotEntry]:
        try:
            entry = await self.client.get_entry(
                pair_id=pair.id,
                data_type=DataTypes.SPOT,
                publisher=self.publisher,
                source=source,
                block_id="pre_confirmed",
            )
        except Exception as e:
            if NO_ENTRY_ERROR in str(e):
                return None
            raise
        return entry  # type: ignore[return-value]

    async def _get_allowed_sources(self) -> Optional[set[int]]:
        """
        Sources the registry lets this publisher push. Others are never
        published and must not count as missing. A read failure keeps the last
        known whitelist; with none yet, every source counts.
        """
        if time.time() - self._allowed_sources_at < ALLOWED_SOURCES_TTL_S:
            return self._allowed_sources
        try:
            sources = await self.client.get_publisher_sources(self.publisher)
            self._allowed_sources = {int(source) for source in sources}
            self._allowed_sources_at = time.time()
        except Exception as e:
            logger.warning(f"Could not read the whitelisted sources: {e}")
        return self._allowed_sources
