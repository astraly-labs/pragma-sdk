from __future__ import annotations

from typing import List, Optional

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
from pragma_sdk.common.types.pair import Pair


class ChainlinkFetcher(EVMOracleFeedFetcher):
    """Fetches prices from Chainlink Ethereum feeds and rebases them to USD."""

    SOURCE = "CHAINLINK"
    feed_configs = build_feed_mapping(
        [
            ("LBTC/BTC", "0x5c29868C58b6e15e2b962943278969Ab6a7D3212", 8),
            ("UNIBTC/BTC", "0x089730f866C6D478398ce1632C7C38677c475EC1", 8),
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
