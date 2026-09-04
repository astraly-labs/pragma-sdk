"""
Off-chain reference prices used to rebase hopped pairs (X/ETH -> X/USD, ...).

A fetcher must never derive an entry from a value read in Pragma's own oracle:
that is a feedback loop, and on 2026-09-04 a thin USDT/USD median (2.04 with two
sources) was multiplied into every USDT-quoted CEX entry (-51%) and every
ETH/BTC-quoted on-chain feed (WSTETH, LBTC, ...). References therefore come from
independent venues only, with a quorum and a spread check, and the caller fails
closed when they are unavailable.
"""

from __future__ import annotations

import asyncio
import statistics
import time

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientSession

from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()

# USD-pegged tickers are rebased at exactly 1.0. A depeg costs a few bps, a
# poisoned oracle median gets multiplied into every pair.
STABLE_TICKERS = frozenset({"USD", "USDT", "USDC", "DAI", "USDPLUS"})

# Kraken uses legacy codes for a few assets.
_KRAKEN_ALIASES = {"BTC": "XBT", "DOGE": "XDG"}


class ReferencePriceError(Exception):
    """Raised when no trustworthy reference price can be established."""


ReferenceSource = Callable[[ClientSession, str], Awaitable[float]]


async def _coinbase(session: ClientSession, base: str) -> float:
    url = f"https://api.coinbase.com/v2/prices/{base}-USD/spot"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"coinbase {base}-USD status {resp.status}")
        data = await resp.json()
        return float(data["data"]["amount"])


async def _kraken(session: ClientSession, base: str) -> float:
    symbol = _KRAKEN_ALIASES.get(base, base)
    url = f"https://api.kraken.com/0/public/Ticker?pair={symbol}USD"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"kraken {symbol}USD status {resp.status}")
        data = await resp.json()
        if data.get("error"):
            raise ReferencePriceError(f"kraken {symbol}USD: {data['error']}")
        ticker = next(iter(data["result"].values()))
        return float(ticker["c"][0])


async def _binance(session: ClientSession, base: str) -> float:
    # USDT-quoted, rebased at 1.0 like every other USDT hop in the SDK.
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"binance {base}USDT status {resp.status}")
        data = await resp.json()
        return float(data["price"])


DEFAULT_SOURCES: Tuple[Tuple[str, ReferenceSource], ...] = (
    ("coinbase", _coinbase),
    ("kraken", _kraken),
    ("binance", _binance),
)


@dataclass
class ReferencePriceProvider:
    """
    Median of independent CEX quotes for <asset>/USD, with a quorum and a
    maximum spread between the venues that answered. Never reads the oracle.
    """

    sources: Tuple[Tuple[str, ReferenceSource], ...] = DEFAULT_SOURCES
    quorum: int = 2
    max_spread: float = 0.02
    timeout_seconds: float = 3.0
    cache_ttl_seconds: float = 10.0
    _cache: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    # One lock per ticker: 20+ fetchers ask for ETH/USD at the same instant on
    # a cold cache, one HTTP round must serve them all.
    _locks: Dict[str, asyncio.Lock] = field(default_factory=dict)

    async def get_price(
        self, base: str, quote: str = "USD", session: Optional[ClientSession] = None
    ) -> float:
        """
        Price of one `base` in `quote`. Stables against USD are 1.0 by design;
        anything else is base/USD divided by quote/USD.
        """
        if session is None:
            async with aiohttp.ClientSession() as own_session:
                return await self.get_price(base, quote, own_session)
        base_usd = await self._usd_price(base, session)
        quote_usd = await self._usd_price(quote, session)
        return base_usd / quote_usd

    async def _usd_price(self, ticker: str, session: ClientSession) -> float:
        if ticker in STABLE_TICKERS:
            return 1.0
        lock = self._locks.setdefault(ticker, asyncio.Lock())
        async with lock:
            cached = self._cache.get(ticker)
            now = time.monotonic()
            if cached is not None and now - cached[1] < self.cache_ttl_seconds:
                return cached[0]
            price = await self._query_sources(ticker, session)
            self._cache[ticker] = (price, time.monotonic())
            return price

    async def _query_sources(self, ticker: str, session: ClientSession) -> float:
        async def one(name: str, source: ReferenceSource) -> Tuple[str, float]:
            async with asyncio.timeout(self.timeout_seconds):
                return name, await source(session, ticker)

        results = await asyncio.gather(
            *(one(name, source) for name, source in self.sources),
            return_exceptions=True,
        )
        quotes: List[Tuple[str, float]] = []
        for name_source, result in zip(self.sources, results):
            if isinstance(result, BaseException):
                logger.warning(
                    "[Reference] %s unavailable for %s/USD: %s",
                    name_source[0],
                    ticker,
                    result,
                )
                continue
            name, price = result
            if price > 0:
                quotes.append((name, price))

        if len(quotes) < self.quorum:
            raise ReferencePriceError(
                f"{ticker}/USD: only {len(quotes)} reference source(s) answered, "
                f"quorum is {self.quorum}"
            )
        prices = [p for _, p in quotes]
        low, high = min(prices), max(prices)
        if (high - low) / low > self.max_spread:
            raise ReferencePriceError(
                f"{ticker}/USD: reference sources disagree by more than "
                f"{self.max_spread:.0%}: {quotes}"
            )
        return statistics.median(prices)


_default_provider: Optional[ReferencePriceProvider] = None


def get_reference_price_provider() -> ReferencePriceProvider:
    """Process-wide provider so the 10s cache is shared across fetchers."""
    global _default_provider
    if _default_provider is None:
        _default_provider = ReferencePriceProvider()
    return _default_provider
