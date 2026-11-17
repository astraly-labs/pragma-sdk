"""
Pairs that must always be published together, in the same transaction.

WSTETH/USD is wstETH/ETH x ETH/USD and STETH/USD trades against ETH: on-chain
they are separate medians, so pushing ETH/USD alone moves the implied
wstETH/ETH and stETH/ETH rates (Vesu, 2026-11-08: +3.56% for ~46s while ETH
fell 3.4% and WSTETH/USD waited for its own 2.5% trigger).
"""

from typing import Dict, FrozenSet, Iterable, List, Mapping, Tuple

from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.types import DataTypes

LINKED_SPOT_PAIRS: Tuple[FrozenSet[str], ...] = (
    frozenset({"ETH/USD", "STETH/USD", "WSTETH/USD"}),
)


def _linked_set(pair_id: str) -> FrozenSet[str]:
    return next((s for s in LINKED_SPOT_PAIRS if pair_id in s), frozenset())


def with_linked_pairs(
    pairs_per_type: Mapping[DataTypes, List[Pair]],
    known_pairs: Mapping[str, Pair],
) -> Dict[DataTypes, List[Pair]]:
    """
    Add to the spot pairs every pair linked to one of them, among the pairs
    this publisher is configured to push (`known_pairs`).
    """
    expanded = {data_type: list(pairs) for data_type, pairs in pairs_per_type.items()}
    spot = expanded.get(DataTypes.SPOT)
    if not spot:
        return expanded
    present = {str(pair) for pair in spot}
    for pair_id in sorted(set().union(*(_linked_set(p) for p in present)) - present):
        if pair_id in known_pairs:
            spot.append(known_pairs[pair_id])
    return expanded


def linked_first(entries: Iterable[Entry]) -> List[Entry]:
    """
    Stable order putting each linked set's entries first and contiguous, so
    the client's pagination keeps them in the same publish_data_entries call.
    """

    def rank(entry: Entry) -> int:
        pair_id = entry.get_pair_id()
        return next(
            (i for i, linked in enumerate(LINKED_SPOT_PAIRS) if pair_id in linked),
            len(LINKED_SPOT_PAIRS),
        )

    return sorted(entries, key=rank)


def largest_linked_batch(entries: Iterable[Entry]) -> int:
    counts = [0] * len(LINKED_SPOT_PAIRS)
    for entry in entries:
        pair_id = entry.get_pair_id()
        for i, linked in enumerate(LINKED_SPOT_PAIRS):
            if pair_id in linked:
                counts[i] += 1
    return max(counts, default=0)
