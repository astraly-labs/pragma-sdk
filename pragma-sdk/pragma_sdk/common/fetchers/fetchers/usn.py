from __future__ import annotations

from typing import List, Optional

from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    build_feed_mapping,
)
from pragma_sdk.common.types.pair import Pair


class USNFetcher(EVMOracleFeedFetcher):
    """Fetches USN/USD price from the fixed rate oracle on Ethereum."""

    SOURCE = "USN_ORACLE"
    feed_configs = build_feed_mapping(
        [
            (
                "USN/USD",
                "0xBd154793659D1E6ea0C58754cEd6807059A421b0",
                18,
                "0x2c4e722e",  # rate() selector
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
