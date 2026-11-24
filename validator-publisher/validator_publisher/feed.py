"""
The pilot feed as a consumer must read it. The pilot Oracle runs the
production class unchanged: it returns a median whatever the number of
sources, and only drops entries an hour older than the newest one. So the
section B rules are applied on this read path, the one the comparator and any
consumer of the pilot use:

- only entries of operators the registry holds ACTIVE, on sources it allows
  and that quote the pair (`PAIR_SOURCES`), count: the Oracle checks the
  registry when an entry is published, not when it is read, so a revoked
  operator's last entries would otherwise stay in the median for up to an
  hour;
- the source of an entry is a label its publisher writes, which nothing
  verifies. A market counts only when a strict majority of the operators
  with a fresh entry on the pair publish it: one operator cannot add markets
  of its own, nor own a market the others do not fetch;
- below MIN_OPERATORS_PER_PAIR operators, or MIN_SOURCES_PER_PAIR markets,
  no new value is given (WITHHELD);
- with no fresh entry at all the feed is STALE.

Operator and market counts are reported separately.
"""

import collections
import statistics

from dataclasses import dataclass
from enum import StrEnum
from typing import Dict, List, Optional, Set

from validator_publisher.chain import OracleSpotEntry, PilotChain
from validator_publisher.deployments import pair_sources
from validator_publisher.source_coverage import MIN_SOURCES_PER_PAIR

# Operators push at least every time_difference (1800 s by default); the
# margin covers the listener poll and the transaction inclusion.
MAX_ENTRY_AGE_S = 2400
MIN_OPERATORS_PER_PAIR = 3
STATUS_ACTIVE = "ACTIVE"


class FeedStatus(StrEnum):
    VALID = "VALID"
    WITHHELD = "WITHHELD"
    STALE = "STALE"


class WithheldReason(StrEnum):
    OPERATORS = "operators"
    MARKETS = "markets"


@dataclass(frozen=True)
class FeedReading:
    pair: str
    status: FeedStatus
    price: Optional[float]
    markets: int
    publishers: int
    newest_age_s: Optional[int]
    # entries of inactive operators, disallowed sources or sources off the pair
    excluded: int = 0
    # markets with fresh entries from no strict majority of the operators
    minority_markets: int = 0
    withheld_reason: Optional[WithheldReason] = None


def read_feed(
    pair: str,
    entries: List[OracleSpotEntry],
    now: int,
    decimals: int,
    active_publishers: Set[int],
    allowed_sources: Set[int],
    max_age_s: int = MAX_ENTRY_AGE_S,
    min_markets: int = MIN_SOURCES_PER_PAIR,
    min_operators: int = MIN_OPERATORS_PER_PAIR,
) -> FeedReading:
    eligible = [
        e
        for e in entries
        if e.publisher in active_publishers and e.source in allowed_sources
    ]
    newest_age = now - max((e.timestamp for e in eligible), default=0)
    fresh = sorted(
        (e for e in eligible if now - e.timestamp <= max_age_s),
        key=lambda e: e.timestamp,
    )
    # one price per operator and market, the newest
    by_market: Dict[int, Dict[int, int]] = collections.defaultdict(dict)
    for entry in fresh:
        by_market[entry.source][entry.publisher] = entry.price
    operators = len({e.publisher for e in fresh})
    markets = {
        source: prices
        for source, prices in by_market.items()
        if 2 * len(prices) > operators
    }

    reason = None
    if not fresh:
        status = FeedStatus.STALE
    elif operators < min_operators:
        status, reason = FeedStatus.WITHHELD, WithheldReason.OPERATORS
    elif len(markets) < min_markets:
        status, reason = FeedStatus.WITHHELD, WithheldReason.MARKETS
    else:
        status = FeedStatus.VALID

    price = None
    if status == FeedStatus.VALID:
        # same two steps as the Oracle: median per market, then across markets
        market_medians = [statistics.median(p.values()) for p in markets.values()]
        price = statistics.median(market_medians) / 10**decimals

    return FeedReading(
        pair=pair,
        status=status,
        price=price,
        markets=len(markets),
        publishers=operators,
        newest_age_s=newest_age if eligible else None,
        excluded=len(entries) - len(eligible),
        minority_markets=len(by_market) - len(markets),
        withheld_reason=reason,
    )


async def read_pilot_feed(
    chain: PilotChain,
    pair: str,
    max_age_s: int = MAX_ENTRY_AGE_S,
    min_operators: int = MIN_OPERATORS_PER_PAIR,
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
        allowed_sources=set(await chain.allowed_sources()) & pair_sources(pair),
        max_age_s=max_age_s,
        min_operators=min_operators,
    )
