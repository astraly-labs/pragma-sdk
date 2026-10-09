"""Guard rails for the Miden pair indices (see pragma_sdk/miden/pair_indices.yaml).

An index is the on-chain key of a pair: it must never change meaning or be reused.
"""

from pathlib import Path

import pytest
import yaml

import pragma_sdk.miden as miden_pkg
from pragma_sdk.miden.client import STARKNET_PAIR_TO_MIDEN_FAUCET

REGISTRY_PATH = Path(miden_pkg.__file__).parent / "pair_indices.yaml"

# Assignments released to production. NEVER edit a line of this table: to stop
# publishing a pair, move it to `retired` in the registry instead. New pairs are
# only added to the registry (and may be appended here once released).
PINNED = {
    "1:0": "BTC/USD",
    "2:0": "ETH/USD",
    "3:0": "WBTC/USD",
    "4:0": "USDT/USD",
    "5:0": "DAI/USD",
    "6:0": "ZEC/USD",
    "7:0": "XMR/USD",
    "8:0": "DASH/USD",
    "9:0": "XAUT/USD",
    "10:0": "PAXG/USD",
    "11:0": "LINK/USD",
    "12:0": "UNI/USD",
    "13:0": "AAVE/USD",
    "14:0": "MORPHO/USD",
    "15:0": "USDC/USD",
}


@pytest.fixture(scope="module")
def registry() -> dict:
    return yaml.safe_load(REGISTRY_PATH.read_text())


def test_registry_matches_the_client_mapping(registry):
    in_client = {idx: pair for pair, idx in STARKNET_PAIR_TO_MIDEN_FAUCET.items()}
    assert registry["active"] == in_client, (
        "pair_indices.yaml and STARKNET_PAIR_TO_MIDEN_FAUCET must be edited together"
    )


def test_pinned_indices_never_change_meaning(registry):
    active, retired = registry["active"], registry["retired"]
    for idx, pair in PINNED.items():
        assert active.get(idx) == pair or retired.get(idx) == pair, (
            f"index {idx} was {pair}: it must stay {pair} (active) or reserved "
            f"(retired), never reassigned"
        )


def test_an_index_is_never_reused(registry):
    active, retired = registry["active"], registry["retired"]
    assert not set(active) & set(retired), "an index is either active or retired"
    pairs = list(active.values()) + list(retired.values())
    assert len(pairs) == len(set(pairs)), "a pair never gets a second index"


def test_indices_are_contiguous_and_new_ones_take_the_next_free(registry):
    indices = list(registry["active"]) + list(registry["retired"])
    assert all(idx.endswith(":0") for idx in indices)
    numbers = sorted(int(idx.split(":")[0]) for idx in indices)
    assert numbers == list(range(1, len(numbers) + 1)), (
        "indices must be 1..N with no gap and no duplicate: a new pair takes max + 1"
    )
    assert numbers[-1] >= max(int(i.split(":")[0]) for i in PINNED)


def test_dropping_a_pair_requires_retiring_its_index(registry):
    """Removing a pinned pair from the client without retiring it is rejected."""
    for idx, pair in PINNED.items():
        assert idx in registry["active"] or idx in registry["retired"], (
            f"{idx} ({pair}) disappeared: move it to `retired`, don't delete it"
        )


def test_legacy_reassignments_are_not_the_current_meaning(registry):
    # Documentation of past mistakes: the old meaning must not be the active one.
    for legacy in registry["legacy_reassignments"]:
        assert registry["active"].get(legacy["index"]) != legacy["pair"]
