"""Fetcher for wstETH conversion rate via the Lido wstETH contract on Ethereum."""

from __future__ import annotations

from typing import List, Optional, Sequence

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    DEFAULT_ETHEREUM_RPC_URLS,
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.pair import Pair


# wstETH contract on Ethereum mainnet
WSTETH_CONTRACT = "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"

# getStETHByWstETH(uint256) selector + ABI-encoded 1e18
WSTETH_RATE_SELECTOR = (
    "0xbb2952fc"
    "0000000000000000000000000000000000000000000000000de0b6b3a7640000"
)


class WstETHRateFetcher(EVMOracleFeedFetcher):
    """
    Fetches WSTETH/USD price using the on-chain wstETH → stETH conversion rate
    from the Lido contract, then hops via ETH/USD from Pragma on-chain.

    WSTETH/USD = getStETHByWstETH(1e18) / 1e18 * ETH/USD
    (stETH ≈ ETH assumption)
    """

    SOURCE = "WSTETH_RATE"
    DEFAULT_RPC_URLS = DEFAULT_ETHEREUM_RPC_URLS
    hop_handler = HopHandler(hopped_currencies={"USD": "ETH"})
    feed_configs = build_feed_mapping(
        [
            ("WSTETH/USD", WSTETH_CONTRACT, 18, WSTETH_RATE_SELECTOR, "WSTETH/ETH"),
        ]
    )

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: str = "mainnet",
        rpc_urls: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(pairs, publisher, api_key, network, rpc_urls)
