"""
Source coverage of this publisher: how many sources allowed by the registry
answered in each poll. Every source that answered is published. The quorum of
MIN_SOURCES_PER_PAIR is counted on the feed, in markets across all operators
(see `validator_publisher.feed`), never per publisher: withholding here would
turn one source outage shared by every operator into a stale feed.
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


class CoverageOrchestrator(Orchestrator):
    """Reports the allowed sources of each poll, logging when a pair degrades."""

    def __init__(
        self,
        *args,
        pairs: Iterable[str],
        allowed_sources: Set[int],
        on_coverage: Optional[Callable[[str, int], None]] = None,
        **kwargs,
    ) -> None:
        self.pairs = list(pairs)
        self.allowed_sources = allowed_sources
        self.on_coverage = on_coverage
        self.degraded: Set[str] = set()
        super().__init__(*args, **kwargs)

    def callback_update_prices(self, entries: List[Entry]) -> None:
        super().callback_update_prices(entries)
        counts = count_allowed_sources(entries, self.allowed_sources)
        for pair in self.pairs:
            found = counts.get(pair, 0)
            if self.on_coverage:
                self.on_coverage(pair, found)
            if found >= MIN_SOURCES_PER_PAIR:
                if pair in self.degraded:
                    self.degraded.discard(pair)
                    logger.info(f"✅ {pair}: {found} allowed sources answered again")
            elif pair not in self.degraded:
                self.degraded.add(pair)
                logger.warning(
                    f"⚠️ {pair}: only {found} allowed source(s) answered, "
                    f"publishing them; the feed needs {MIN_SOURCES_PER_PAIR} markets "
                    "across operators"
                )

    async def refresh_allowed_sources_forever(self, chain: PilotChain) -> None:
        while True:
            await asyncio.sleep(ALLOWED_SOURCES_REFRESH_S)
            try:
                self.allowed_sources = set(await chain.allowed_sources())
            except Exception as e:
                logger.warning(f"Could not refresh the allowed sources: {e}")
