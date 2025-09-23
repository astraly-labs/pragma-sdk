from __future__ import annotations

from typing import List, Optional

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
from pragma_sdk.common.types.pair import Pair


class Re7OnChainFetcher(EVMOracleFeedFetcher):
    """Fetches mRe7 feeds that expose ``lastAnswer`` on Ethereum."""

    SOURCE = "RE7_ONCHAIN"
    feed_configs = build_feed_mapping(
        [
            (
                "MRE7BTC/USD",
                "0x9de073685AEb382B7c6Dd0FB93fa0AEF80eB8967",
                8,
                "0xbb23ae25",
                "MRE7BTC/BTC",
            ),
            (
                "MRE7YIELD/USD",
                "0x0a2a51f2f206447dE3E3a80FCf92240244722395",
                8,
                "0xbb23ae25",
            ),
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
