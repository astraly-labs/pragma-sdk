from __future__ import annotations

from typing import List, Optional, Sequence

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    DEFAULT_ETHEREUM_RPC_URLS,
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.pair import Pair


class RedstoneFetcher(EVMOracleFeedFetcher):
    """Fetches prices from Redstone Ethereum feeds and rebases them to USD."""

    SOURCE = "REDSTONE"
    feed_configs = build_feed_mapping(
        [
            ("LBTC/BTC", "0xb415eAA355D8440ac7eCB602D3fb67ccC1f0bc81", 8),
        ]
    )

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: str = "mainnet",
    ) -> None:
        super().__init__(pairs, publisher, api_key, network)


class WstETHRedstoneFetcher(EVMOracleFeedFetcher):
    """
    Fetches WSTETH/USD using the Redstone WSTETH/STETH feed on Ethereum,
    then hops via ETH/USD from Pragma on-chain.

    WSTETH/USD = redstone_wsteth_steth * ETH/USD
    (stETH ≈ ETH assumption)
    """

    SOURCE = "REDSTONE_WSTETH"
    DEFAULT_RPC_URLS = DEFAULT_ETHEREUM_RPC_URLS
    hop_handler = HopHandler(hopped_currencies={"USD": "ETH"})
    feed_configs = build_feed_mapping(
        [
            ("WSTETH/USD", "0xa7B0247d2dA6B11FF2740491cB433a1520d5DA98", 8, "WSTETH/ETH"),
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
