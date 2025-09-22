from __future__ import annotations

from typing import List, Optional

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
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
