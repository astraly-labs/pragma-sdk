"""Fetcher for SUSN (Staked USN) price in USD."""

from __future__ import annotations

import asyncio
import time
from typing import List, Optional, Sequence

from aiohttp import ClientSession

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetchers.evm_oracle import (
    EVMOracleFeedFetcher,
    FeedConfig,
)
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair


# ERC4626 convertToAssets(uint256 shares) selector
CONVERT_TO_ASSETS_SELECTOR = "0x07a2d13a"
# 1e18 in hex (padded to 32 bytes)
ONE_SHARE_18_DECIMALS = (
    "0000000000000000000000000000000000000000000000000de0b6b3a7640000"
)

# Contract addresses
SUSN_VAULT_ADDRESS = "0xE24a3DC889621612422A64E6388927901608B91D"
USN_ORACLE_ADDRESS = "0xBd154793659D1E6ea0C58754cEd6807059A421b0"
USN_RATE_SELECTOR = "0x2c4e722e"


class sUSNFetcher(EVMOracleFeedFetcher):
    """
    Fetches SUSN/USD price by combining:
    1. SUSN/USN rate from ERC4626 vault (convertToAssets)
    2. USN/USD price from fixed rate oracle (rate)

    Result: SUSN/USD = (SUSN/USN) * (USN/USD)
    """

    SOURCE = "SUSN_VAULT"

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: str = "mainnet",
        rpc_urls: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(pairs, publisher, api_key, network, rpc_urls)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        tasks = [
            asyncio.ensure_future(self.fetch_pair(pair, session)) for pair in self.pairs
        ]
        return list(await asyncio.gather(*tasks, return_exceptions=True))

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        """Fetch SUSN/USD price."""

        if str(pair) != "SUSN/USD":
            return PublisherFetchError(
                f"sUSNFetcher only supports SUSN/USD pair, got {pair}"
            )

        # Fetch SUSN/USN rate from vault and USN/USD price in parallel
        susn_usn_task = self._read_vault_rate(session)
        usn_usd_task = self._read_usn_price(session)

        results = await asyncio.gather(
            susn_usn_task, usn_usd_task, return_exceptions=True
        )

        susn_usn_result = results[0]
        usn_usd_result = results[1]

        if isinstance(susn_usn_result, PublisherFetchError):
            return susn_usn_result
        if isinstance(usn_usd_result, PublisherFetchError):
            return usn_usd_result

        # Both are in 18 decimals, calculate SUSN/USD
        susn_usn_ratio = susn_usn_result / (10**18)
        usn_usd_price = usn_usd_result / (10**18)

        susn_usd_price = susn_usn_ratio * usn_usd_price

        # Convert to integer with pair decimals (8 for USD pairs)
        price_int = int(susn_usd_price * (10 ** pair.decimals()))
        timestamp = int(time.time())

        return SpotEntry(
            pair_id=pair.id,
            price=price_int,
            volume=0,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

    async def _read_vault_rate(
        self, session: ClientSession
    ) -> float | PublisherFetchError:
        """Call convertToAssets on the SUSN vault."""
        calldata = CONVERT_TO_ASSETS_SELECTOR + ONE_SHARE_18_DECIMALS
        vault_config = FeedConfig(
            contract_address=SUSN_VAULT_ADDRESS,
            decimals=18,
            selector=calldata,
        )
        return await self._read_feed_value(session, vault_config)

    async def _read_usn_price(
        self, session: ClientSession
    ) -> float | PublisherFetchError:
        """Call rate() on the USN oracle - reuse parent's _read_feed_value."""
        usn_config = FeedConfig(
            contract_address=USN_ORACLE_ADDRESS,
            decimals=18,
            selector=USN_RATE_SELECTOR,
        )
        return await self._read_feed_value(session, usn_config)
