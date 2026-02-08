from __future__ import annotations

from typing import List, Optional, Sequence

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.pair import Pair


class ChainlinkFetcher(EVMOracleFeedFetcher):
    """Fetches prices from Chainlink Ethereum feeds and rebases them to USD."""

    SOURCE = "CHAINLINK"
    feed_configs = build_feed_mapping(
        [
            ("LBTC/BTC", "0x5c29868C58b6e15e2b962943278969Ab6a7D3212", 8),
            ("UNIBTC/BTC", "0x861d15F8a4059cb918bD6F3670adAEB1220B298f", 18),
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


ARBITRUM_RPC_URLS: Sequence[str] = (
    "https://arbitrum.drpc.org",
    "https://rpc.sentio.xyz/arbitrum-one",
    "https://arb1.lava.build",
    "https://arbitrum-one.publicnode.com",
    "https://arbitrum.llamarpc.com",
)


class WstETHChainlinkFetcher(EVMOracleFeedFetcher):
    """
    Fetches WSTETH/USD using the Chainlink WSTETH/ETH feed on Arbitrum,
    then hops via ETH/USD from Pragma on-chain.

    WSTETH/USD = chainlink_wsteth_eth * ETH/USD
    """

    SOURCE = "CHAINLINK_WSTETH"
    DEFAULT_RPC_URLS = ARBITRUM_RPC_URLS
    hop_handler = HopHandler(hopped_currencies={"USD": "ETH"})
    feed_configs = build_feed_mapping(
        [
            ("WSTETH/USD", "0xB1552C5e96B312d0Bf8b554186F846C40614a540", 18, "WSTETH/ETH"),
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
