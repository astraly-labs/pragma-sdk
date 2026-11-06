"""
Source quorum: a spot pair is published only when at least MIN_SOURCES_PER_PAIR
sources allowed by the registry answered in the same poll. Below that the pair
is withheld, never published on fewer sources.
"""

import asyncio
import collections
import logging

from typing import Callable, Dict, Iterable, List, Optional, Set

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.types import DataTypes
from price_pusher.orchestrator import Orchestrator

from validator_publisher.chain import PilotChain

logger = logging.getLogger(__name__)

MIN_SOURCES_PER_PAIR = 4
ALLOWED_SOURCES_REFRESH_S = 60


def count_allowed_sources(
    entries: Iterable[Entry], allowed: Set[int]
) -> Dict[str, int]:
    sources: Dict[str, Set[int]] = collections.defaultdict(set)
    for entry in entries:
        if entry.get_asset_type() == DataTypes.SPOT and entry.base.source in allowed:
            sources[entry.get_pair_id()].add(entry.base.source)
    return {pair: len(found) for pair, found in sources.items()}


class QuorumOrchestrator(Orchestrator):
    """
    After each poll, drops the pending prices of every pair short of the
    quorum. The listener then sees no data for it and asks for no push, and no
    batch carries it, not even prices kept from an earlier poll.
    """

    def __init__(
        self,
        *args,
        pairs: Iterable[str],
        allowed_sources: Set[int],
        min_sources: int = MIN_SOURCES_PER_PAIR,
        on_quorum: Optional[Callable[[str, int], None]] = None,
        **kwargs,
    ) -> None:
        self.pairs = list(pairs)
        self.allowed_sources = allowed_sources
        self.min_sources = min_sources
        self.on_quorum = on_quorum
        self.withheld: Set[str] = set()
        super().__init__(*args, **kwargs)

    def callback_update_prices(self, entries: List[Entry]) -> None:
        super().callback_update_prices(entries)
        counts = count_allowed_sources(entries, self.allowed_sources)
        for pair in self.pairs:
            found = counts.get(pair, 0)
            if self.on_quorum:
                self.on_quorum(pair, found)
            if found >= self.min_sources:
                if pair in self.withheld:
                    self.withheld.discard(pair)
                    logger.info(f"✅ {pair}: {found} allowed sources, publishing again")
                continue
            self._drop_pending(pair)
            if pair not in self.withheld:
                self.withheld.add(pair)
                logger.warning(
                    f"⛔ {pair} withheld: {found} allowed source(s) answered, "
                    f"{self.min_sources} required"
                )

    def _drop_pending(self, pair: str) -> None:
        pending = self.latest_prices.get(pair)
        if pending is None:
            return
        pending.pop(DataTypes.SPOT, None)
        if not pending:
            # the listeners hold this dict: mutate it, never rebind it
            del self.latest_prices[pair]

    async def refresh_allowed_sources_forever(self, chain: PilotChain) -> None:
        while True:
            await asyncio.sleep(ALLOWED_SOURCES_REFRESH_S)
            try:
                self.allowed_sources = set(await chain.allowed_sources())
            except Exception as e:
                logger.warning(f"Could not refresh the allowed sources: {e}")
