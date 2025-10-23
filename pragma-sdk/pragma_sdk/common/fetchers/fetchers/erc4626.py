"""Fetcher for ERC4626 vault exchange rates on Ethereum."""

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

DEFAULT_ETHEREUM_RPC_URLS: Sequence[str] = (
    "https://ethereum.publicnode.com",
    "https://eth.llamarpc.com",
    "https://rpc.mevblocker.io",
    "https://1rpc.io/eth",
    "https://eth.merkle.io",
    "https://rpc.flashbots.net",
)

# ERC4626 convertToAssets(uint256 shares) selector
CONVERT_TO_ASSETS_SELECTOR = "0x07a2d13a"

# 1e18 in hex (padded to 32 bytes) - 1 share in 18 decimals
ONE_SHARE_18_DECIMALS = (
    "0000000000000000000000000000000000000000000000000de0b6b3a7640000"
)


@dataclass(slots=True)
class ERC4626Config:
    """Configuration for an ERC4626 vault."""

    vault_address: str
    decimals: int = 18
    shares_amount: str = ONE_SHARE_18_DECIMALS
    underlying_pair: Optional[str] = None


class ERC4626RateFetcher(FetcherInterfaceT):
    """
    Fetches exchange rates from ERC4626 vaults using convertToAssets.

    This fetcher calls convertToAssets(shares) on ERC4626 vaults to get
    the exchange rate between vault shares and underlying assets.
    """

    SOURCE: str = "ERC4626"
    hop_handler: HopHandler = HopHandler(hopped_currencies={})
    feed_configs: Dict[str, ERC4626Config] = {}

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
        resolved_pairs: List[tuple[Pair, Pair, ERC4626Config]] = []
        errors: List[PublisherFetchError] = []
        requires_hop = False

        for requested_pair in self.pairs:
            requested_key = str(requested_pair)
            config = self.feed_configs.get(requested_key)

            if config is not None:
                underlying_pair_str = config.underlying_pair or requested_key
                if underlying_pair_str != requested_key:
                    base_ticker, quote_ticker = underlying_pair_str.split("/")
                    underlying_pair = Pair.from_tickers(base_ticker, quote_ticker)
                    if quote_ticker != requested_pair.quote_currency.id:
                        requires_hop = True
                else:
                    underlying_pair = requested_pair

                resolved_pairs.append((requested_pair, underlying_pair, config))
                continue

            hopped_pair = self.hop_handler.get_hop_pair(requested_pair)
            if hopped_pair is not None:
                config = self.feed_configs.get(str(hopped_pair))
                if config is None:
                    errors.append(
                        PublisherFetchError(
                            f"No vault configuration for {hopped_pair} in {self.__class__.__name__}"
                        )
                    )
                    continue

                requires_hop = True
                resolved_pairs.append((requested_pair, hopped_pair, config))
                continue

            errors.append(
                PublisherFetchError(
                    f"No vault configuration for {requested_pair} in {self.__class__.__name__}"
                )
            )

        hop_prices: Optional[Dict[Pair, float]] = None
        if requires_hop:
            hop_prices = await self.hop_handler.get_hop_prices(self.client)

        tasks = [
            asyncio.ensure_future(
                self._fetch_single_pair(
                    requested_pair=pair,
                    underlying_pair=underlying_pair,
                    session=session,
                    hop_prices=hop_prices,
                    config=config,
                )
            )
            for pair, underlying_pair, config in resolved_pairs
        ]

        results = list(await asyncio.gather(*tasks, return_exceptions=True))
        return errors + results

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        """Required abstract method but we do not use it directly."""

        return PublisherFetchError("ERC4626RateFetcher uses custom fetch logic")

    async def _fetch_single_pair(
        self,
        requested_pair: Pair,
        underlying_pair: Pair,
        session: ClientSession,
        hop_prices: Optional[Dict[Pair, float]],
        config: ERC4626Config,
    ) -> Entry | PublisherFetchError:
        """Fetch and assemble a spot entry for a single pair."""

        assets_amount = await self._read_vault_rate(session, config)
        if isinstance(assets_amount, PublisherFetchError):
            return assets_amount

        # The ratio represents how many underlying assets you get per share
        ratio = assets_amount / (10**config.decimals)

        price = ratio
        if underlying_pair != requested_pair:
            if hop_prices is None:
                return PublisherFetchError(
                    f"Missing hop prices for {requested_pair} in {self.__class__.__name__}"
                )

            hop_pair = Pair.from_tickers(
                underlying_pair.quote_currency.id, requested_pair.quote_currency.id
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

    async def _read_vault_rate(
        self, session: ClientSession, config: ERC4626Config
    ) -> float | PublisherFetchError:
        """Call convertToAssets on the ERC4626 vault, rotating RPCs on failure."""

        # Encode calldata: selector + shares parameter
        calldata = CONVERT_TO_ASSETS_SELECTOR + config.shares_amount

        rpc_candidates = list(self._rpc_urls)
        for _ in range(len(rpc_candidates)):
            rpc_url = self._next_rpc_url()
            payload = {
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "eth_call",
                "params": [
                    {"to": config.vault_address, "data": calldata},
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

            # ERC4626 returns uint256, shouldn't need signed conversion
            return float(value)

        return PublisherFetchError(
            f"All Ethereum RPCs failed while calling vault for {config.vault_address}"
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


def build_erc4626_mapping(entries: Iterable[tuple]) -> Dict[str, ERC4626Config]:
    """
    Utility to build ``feed_configs`` dictionaries for ERC4626 vaults.

    Accepts entries shaped as ``(pair, vault_address[, decimals[, shares_amount[, underlying_pair]]])``.

    Examples:
        - ("sUSN/USN", "0xE24a3DC889621612422A64E6388927901608B91D")
        - ("sUSN/USN", "0xE24a3DC889621612422A64E6388927901608B91D", 18)
    """

    mapping: Dict[str, ERC4626Config] = {}
    for entry in entries:
        if len(entry) == 2:
            pair_str, vault_address = entry
            decimals = 18
            shares_amount = ONE_SHARE_18_DECIMALS
            underlying_pair = pair_str
        elif len(entry) == 3:
            pair_str, vault_address, decimals = entry
            shares_amount = ONE_SHARE_18_DECIMALS
            underlying_pair = pair_str
        elif len(entry) == 4:
            pair_str, vault_address, decimals, shares_amount = entry
            underlying_pair = pair_str
        elif len(entry) == 5:
            pair_str, vault_address, decimals, shares_amount, underlying_pair = entry
        else:
            raise ValueError(
                "ERC4626 mapping entries must contain 2 to 5 elements: (pair, vault_address[, decimals[, shares_amount[, underlying_pair]]])."
            )

        config = ERC4626Config(
            vault_address=vault_address,
            decimals=decimals,
            shares_amount=shares_amount,
            underlying_pair=underlying_pair if underlying_pair != pair_str else None,
        )

        mapping[pair_str] = config
        if config.underlying_pair is not None:
            mapping[config.underlying_pair] = config

    return mapping
