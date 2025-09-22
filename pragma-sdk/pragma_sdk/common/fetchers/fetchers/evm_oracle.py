"""Helpers for fetchers reading on-chain feeds from Ethereum."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from aiohttp import ClientSession

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair


logger = get_pragma_sdk_logger()


LATEST_ANSWER_SELECTOR = "0x50d25bcd"

ETHEREUM_RPC_URLS = [
    "https://rpc.ankr.com/eth",
    "https://eth.llamarpc.com",
    "https://cloudflare-eth.com",
    "https://eth.llamarpc.com",
    "https://ethereum-rpc.publicnode.com",
    "https://rpc.mevblocker.io",
]


@dataclass(slots=True)
class FeedConfig:
    """Configuration for an on-chain price feed."""

    contract_address: str
    decimals: int = 8


class EVMOracleFeedFetcher(FetcherInterfaceT):
    """Base fetcher for Ethereum on-chain feeds returning ratios via ``latestAnswer``."""

    SOURCE: str = "EVM_ORACLE"
    hop_handler: HopHandler = HopHandler(hopped_currencies={"USD": "BTC"})
    feed_configs: Dict[str, FeedConfig] = {}

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: str = "mainnet",
        rpc_urls: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(pairs, publisher, api_key, network)

        self._rpc_urls: List[str] = list(rpc_urls) if rpc_urls else ETHEREUM_RPC_URLS
        if len(self._rpc_urls) == 0:
            raise ValueError("Ethereum RPC URLs list cannot be empty")
        self._rpc_index = 0
        self._request_id = 0

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        pairs_to_fetch: List[tuple[Pair, Pair]] = []
        requires_hop = False
        for requested_pair in self.pairs:
            hopped_pair = self.hop_handler.get_hop_pair(requested_pair)
            if hopped_pair is not None:
                requires_hop = True
                pairs_to_fetch.append((requested_pair, hopped_pair))
            else:
                pairs_to_fetch.append((requested_pair, requested_pair))

        hop_prices: Optional[Dict[Pair, float]] = None
        if requires_hop:
            hop_prices = await self.hop_handler.get_hop_prices(self.client)

        tasks = [
            asyncio.ensure_future(
                self._fetch_single_pair(
                    requested_pair=pair,
                    feed_pair=feed_pair,
                    session=session,
                    hop_prices=hop_prices,
                )
            )
            for pair, feed_pair in pairs_to_fetch
        ]

        return list(await asyncio.gather(*tasks, return_exceptions=True))

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        """Required abstract method but we do not use it directly."""

        return PublisherFetchError("EVMOracleFeedFetcher uses custom fetch logic")

    async def _fetch_single_pair(
        self,
        requested_pair: Pair,
        feed_pair: Pair,
        session: ClientSession,
        hop_prices: Optional[Dict[Pair, float]],
    ) -> Entry | PublisherFetchError:
        """Fetch and assemble a spot entry for a single pair."""

        feed_key = str(feed_pair)
        config = self.feed_configs.get(feed_key)
        if config is None:
            return PublisherFetchError(
                f"No feed configuration for {feed_key} in {self.__class__.__name__}"
            )

        latest_answer = await self._read_latest_answer(session, config.contract_address)
        if isinstance(latest_answer, PublisherFetchError):
            return latest_answer

        ratio = latest_answer / (10**config.decimals)

        price = ratio
        if feed_pair != requested_pair:
            if hop_prices is None:
                return PublisherFetchError(
                    f"Missing hop prices for {requested_pair} in {self.__class__.__name__}"
                )

            hop_pair = Pair.from_tickers(
                feed_pair.quote_currency.id, requested_pair.quote_currency.id
            )
            hop_price = hop_prices.get(hop_pair)
            if hop_price is None:
                return PublisherFetchError(
                    f"Hop price for {hop_pair} not found while pricing {requested_pair}"
                )
            price = ratio * hop_price

        price_int = int(price * (10 ** requested_pair.decimals()))
        timestamp = int(time.time())

        return SpotEntry(
            pair_id=requested_pair.id,
            price=price_int,
            volume=0,
            timestamp=timestamp,
            source=self.SOURCE,
            publisher=self.publisher,
        )

    async def _read_latest_answer(
        self, session: ClientSession, contract_address: str
    ) -> float | PublisherFetchError:
        """Call ``latestAnswer`` on the configured feed, rotating RPCs on failure."""

        rpc_candidates = list(self._rpc_urls)
        for _ in range(len(rpc_candidates)):
            rpc_url = self._next_rpc_url()
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "eth_call",
                "params": [
                    {"to": contract_address, "data": LATEST_ANSWER_SELECTOR},
                    "latest",
                ],
            }

            try:
                async with session.post(
                    rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "%s received non-200 status %s from %s",
                            self.__class__.__name__,
                            resp.status,
                            rpc_url,
                        )
                        continue

                    data = await resp.json()
            except Exception as exc:  # pragma: no cover - defensive, network failure
                logger.warning(
                    "%s failed RPC call via %s: %s",
                    self.__class__.__name__,
                    rpc_url,
                    exc,
                )
                continue

            result = data.get("result") if isinstance(data, dict) else None
            if result is None:
                message = (
                    data.get("error", {}).get("message")
                    if isinstance(data, dict)
                    else data
                )
                logger.warning(
                    "%s got empty result from %s: %s",
                    self.__class__.__name__,
                    rpc_url,
                    message,
                )
                continue

            try:
                value = int(result, 16)
            except ValueError as exc:
                logger.error(
                    "%s received invalid hex result %s: %s",
                    self.__class__.__name__,
                    result,
                    exc,
                )
                continue

            # Convert from uint256 to signed int256 if needed.
            if value >= 2**255:
                value -= 2**256

            return float(value)

        return PublisherFetchError(
            f"All Ethereum RPCs failed while calling latestAnswer for {contract_address}"
        )

    def _next_rpc_url(self) -> str:
        url = self._rpc_urls[self._rpc_index]
        self._rpc_index = (self._rpc_index + 1) % len(self._rpc_urls)
        return url

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def format_url(self, pair: Pair) -> str:
        None


def build_feed_mapping(
    entries: Iterable[tuple[str, str, int]],
) -> Dict[str, FeedConfig]:
    """Utility to build ``feed_configs`` dictionaries.

    Args:
        entries: iterable of tuples (pair_str, contract_address, decimals)
    """

    mapping: Dict[str, FeedConfig] = {}
    for pair_str, contract_address, decimals in entries:
        mapping[pair_str] = FeedConfig(
            contract_address=contract_address, decimals=decimals
        )
    return mapping
