"""
The pilot feed as a consumer must read it. The pilot Oracle runs the
production class unchanged: it returns a median whatever the number of
sources, and only drops entries an hour older than the newest one. So the
section B rules are applied on this read path, the one the comparator and any
consumer of the pilot use:

- only entries of operators the registry holds ACTIVE, on sources it allows,
  count: the Oracle checks the registry when an entry is published, not when
  it is read, so a revoked operator's last entries would otherwise stay in
  the median for up to an hour;
- the quorum counts underlying markets with a fresh entry, across every
  operator, never publisher processes;
- below MIN_SOURCES_PER_PAIR markets no new value is given (WITHHELD);
- with no fresh entry at all the feed is STALE.

Publisher and market counts are reported separately.
"""

import collections
import statistics

from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, List, Optional, Set

from validator_publisher.chain import OracleSpotEntry, PilotChain
from validator_publisher.source_coverage import MIN_SOURCES_PER_PAIR

# Operators push at least every time_difference (1800 s by default); the
# margin covers the listener poll and the transaction inclusion.
MAX_ENTRY_AGE_S = 2400
STATUS_ACTIVE = "ACTIVE"


class FeedStatus(StrEnum):
    VALID = "VALID"
    WITHHELD = "WITHHELD"
    STALE = "STALE"


@dataclass(frozen=True)
class FeedReading:
    pair: str
    status: FeedStatus
    price: Optional[float]
    markets: int
    publishers: int
    newest_age_s: Optional[int]
    # entries of inactive operators or disallowed sources
    excluded: int = 0


def read_feed(
    pair: str,
    entries: List[OracleSpotEntry],
    now: int,
    decimals: int,
    active_publishers: Set[int],
    allowed_sources: Set[int],
    max_age_s: int = MAX_ENTRY_AGE_S,
    min_markets: int = MIN_SOURCES_PER_PAIR,
) -> FeedReading:
    eligible = [
        e
        for e in entries
        if e.publisher in active_publishers and e.source in allowed_sources
    ]
    newest_age = now - max((e.timestamp for e in eligible), default=0)
    fresh = [e for e in eligible if now - e.timestamp <= max_age_s]
    by_market: Dict[int, List[int]] = collections.defaultdict(list)
    for entry in fresh:
        by_market[entry.source].append(entry.price)
    publishers = len({e.publisher for e in fresh})

    if not fresh:
        status = FeedStatus.STALE
    elif len(by_market) < min_markets:
        status = FeedStatus.WITHHELD
    else:
        status = FeedStatus.VALID

    price = None
    if status == FeedStatus.VALID:
        # same two steps as the Oracle: median per market, then across markets
        market_medians = [statistics.median(p) for p in by_market.values()]
        price = statistics.median(market_medians) / 10**decimals

    return FeedReading(
        pair=pair,
        status=status,
        price=price,
        markets=len(by_market),
        publishers=publishers,
        newest_age_s=newest_age if eligible else None,
        excluded=len(entries) - len(eligible),
    )


async def read_pilot_feed(
    chain: PilotChain, pair: str, max_age_s: int = MAX_ENTRY_AGE_S
) -> FeedReading:
    entries = await chain.spot_entries(pair)
    active = {
        publisher
        for publisher in {e.publisher for e in entries}
        if await chain.publisher_status(publisher) == STATUS_ACTIVE
    }
    return read_feed(
        pair,
        entries,
        now=await chain.block_timestamp(),
        decimals=await chain.decimals(pair),
        active_publishers=active,
        allowed_sources=set(await chain.allowed_sources()),
        max_age_s=max_age_s,
    )
