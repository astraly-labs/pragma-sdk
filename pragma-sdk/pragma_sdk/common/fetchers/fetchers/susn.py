from __future__ import annotations

from typing import List, Optional

from pragma_sdk.common.fetchers.fetchers.erc4626 import (
    ERC4626RateFetcher,
    build_erc4626_mapping,
)
from pragma_sdk.common.types.pair import Pair


class sUSNFetcher(ERC4626RateFetcher):
    """Fetches sUSN/USN exchange rate from the sUSN ERC4626 vault on Ethereum."""

    SOURCE = "SUSN_VAULT"
    feed_configs = build_erc4626_mapping(
        [
            (
                "sUSN/USN",
                "0xE24a3DC889621612422A64E6388927901608B91D",
                18,  # decimals
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
