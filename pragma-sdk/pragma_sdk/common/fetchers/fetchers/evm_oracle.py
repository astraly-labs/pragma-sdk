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


DEFAULT_FEED_SELECTOR = "0x50d25bcd"

DEFAULT_ETHEREUM_RPC_URLS: Sequence[str] = (
    "https://ethereum.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.mevblocker.io",
    "https://1rpc.io/eth",
    "https://eth.merkle.io",
    "https://rpc.flashbots.net",
)


@dataclass(slots=True)
class FeedConfig:
    """Configuration for an on-chain price feed."""

    contract_address: str
    decimals: int = 8
    selector: str = DEFAULT_FEED_SELECTOR
    feed_pair: Optional[str] = None


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

        default_rpcs = getattr(self, "DEFAULT_RPC_URLS", DEFAULT_ETHEREUM_RPC_URLS)
        self._rpc_urls: List[str] = list(rpc_urls) if rpc_urls else list(default_rpcs)
        if len(self._rpc_urls) == 0:
            raise ValueError("Ethereum RPC URLs list cannot be empty")
        self._rpc_index = 0
        self._request_id = 0

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        resolved_pairs: List[tuple[Pair, Pair, FeedConfig]] = []
        errors: List[PublisherFetchError] = []
        requires_hop = False

        for requested_pair in self.pairs:
            requested_key = str(requested_pair)
            config = self.feed_configs.get(requested_key)

            if config is not None:
                feed_pair_str = config.feed_pair or requested_key
                if feed_pair_str != requested_key:
                    base_ticker, quote_ticker = feed_pair_str.split("/")
                    feed_pair = Pair.from_tickers(base_ticker, quote_ticker)
                    if quote_ticker != requested_pair.quote_currency.id:
                        requires_hop = True
                else:
                    feed_pair = requested_pair

                resolved_pairs.append((requested_pair, feed_pair, config))
                continue

            hopped_pair = self.hop_handler.get_hop_pair(requested_pair)
            if hopped_pair is not None:
                config = self.feed_configs.get(str(hopped_pair))
                if config is None:
                    errors.append(
                        PublisherFetchError(
                            f"No feed configuration for {hopped_pair} in {self.__class__.__name__}"
                        )
                    )
                    continue

                requires_hop = True
                resolved_pairs.append((requested_pair, hopped_pair, config))
                continue

            errors.append(
                PublisherFetchError(
                    f"No feed configuration for {requested_pair} in {self.__class__.__name__}"
                )
            )

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
                    config=config,
                )
            )
            for pair, feed_pair, config in resolved_pairs
        ]

        results = list(await asyncio.gather(*tasks, return_exceptions=True))
        return errors + results

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
        config: FeedConfig,
    ) -> Entry | PublisherFetchError:
        """Fetch and assemble a spot entry for a single pair."""

        latest_answer = await self._read_feed_value(session, config)
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

    async def _read_feed_value(
        self, session: ClientSession, config: FeedConfig
    ) -> float | PublisherFetchError:
        """Call the configured feed selector, rotating RPCs on failure."""

        rpc_candidates = list(self._rpc_urls)
        for _ in range(len(rpc_candidates)):
            rpc_url = self._next_rpc_url()
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "eth_call",
                "params": [
                    {"to": config.contract_address, "data": config.selector},
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
            f"All Ethereum RPCs failed while calling feed for {config.contract_address}"
        )

    def _next_rpc_url(self) -> str:
        url = self._rpc_urls[self._rpc_index]
        self._rpc_index = (self._rpc_index + 1) % len(self._rpc_urls)
        return url

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def format_url(self, pair: Pair) -> str:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not use HTTP endpoints per pair."
        )


def build_feed_mapping(entries: Iterable[tuple]) -> Dict[str, FeedConfig]:
    """Utility to build ``feed_configs`` dictionaries.

    Accepts entries shaped as ``(pair, contract, decimals[, selector[, feed_pair]])``.
    """

    mapping: Dict[str, FeedConfig] = {}
    for entry in entries:
        if len(entry) == 3:
            pair_str, contract_address, decimals = entry
            selector = DEFAULT_FEED_SELECTOR
            feed_pair = pair_str
        elif len(entry) == 4:
            pair_str, contract_address, decimals, optional = entry
            if isinstance(optional, str) and optional.startswith("0x"):
                selector = optional
                feed_pair = pair_str
            else:
                selector = DEFAULT_FEED_SELECTOR
                feed_pair = optional
        elif len(entry) == 5:
            pair_str, contract_address, decimals, selector, feed_pair = entry
        else:
            raise ValueError(
                "Feed mapping entries must contain 3 to 5 elements: (pair, contract, decimals[, selector[, feed_pair]])."
            )

        config = FeedConfig(
            contract_address=contract_address,
            decimals=decimals,
            selector=selector or DEFAULT_FEED_SELECTOR,
            feed_pair=feed_pair if feed_pair != pair_str else None,
        )

        mapping[pair_str] = config
        if config.feed_pair is not None:
            mapping[config.feed_pair] = config

    return mapping
