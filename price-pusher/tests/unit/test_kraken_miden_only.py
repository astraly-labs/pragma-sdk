"""
Kraken must not reach Starknet until the KRAKEN source is whitelisted in the
PublisherRegistry: a single non-whitelisted entry makes the oracle reject the
whole publish batch it sits in. The fetcher is therefore restricted to pairs
that only live in `miden_only` config groups.
"""

from pathlib import Path

import pytest
import yaml

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.fetchers import KrakenFetcher

from price_pusher.configs.fetchers import (
    FETCHER_RESTRICTED_PAIRS,
    KRAKEN_MIDEN_ONLY_PAIRS,
)
from price_pusher.configs.price_config import PriceConfig
from price_pusher.core.fetchers import add_all_fetchers

MAINNET_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "infra"
    / "price-pusher"
    / "config"
    / "config.mainnet.yaml"
)


def _config(*pairs: str) -> PriceConfig:
    return PriceConfig(
        pairs={"spot": list(pairs)}, time_difference=1800, price_deviation=0.01
    )


def test_kraken_is_restricted():
    assert FETCHER_RESTRICTED_PAIRS[KrakenFetcher] == KRAKEN_MIDEN_ONLY_PAIRS


def test_kraken_pairs_never_belong_to_a_starknet_group():
    # Raw YAML on purpose: the miden_only flag may not exist on this branch
    # yet, and a group without it is a Starknet group.
    groups = yaml.safe_load(MAINNET_CONFIG.read_text())
    starknet_pairs = {
        pair.replace(" ", "").upper()
        for group in groups
        if not group.get("miden_only")
        for pair in (group.get("pairs") or {}).get("spot", [])
    }
    leaked = KRAKEN_MIDEN_ONLY_PAIRS & starknet_pairs
    assert not leaked, f"Kraken pairs pushed to Starknet without a whitelist: {leaked}"


@pytest.mark.asyncio
async def test_kraken_not_built_for_a_starknet_only_config():
    client = await add_all_fetchers(
        FetcherClient(), "PRAGMA", [_config("BTC/USD", "ETH/USD")]
    )
    assert not [f for f in client.fetchers if isinstance(f, KrakenFetcher)]


@pytest.mark.asyncio
async def test_kraken_only_gets_the_miden_pairs():
    client = await add_all_fetchers(
        FetcherClient(), "PRAGMA", [_config("BTC/USD", "LINK/USD", "UNI/USD")]
    )
    [kraken] = [f for f in client.fetchers if isinstance(f, KrakenFetcher)]
    assert {str(p) for p in kraken.pairs} == {"LINK/USD", "UNI/USD"}
