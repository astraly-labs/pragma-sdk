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


async def _bitstamp(session: ClientSession, base: str) -> float:
    url = f"https://www.bitstamp.net/api/v2/ticker/{base.lower()}usd/"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"bitstamp {base}usd status {resp.status}")
        data = await resp.json()
        if float(data.get("volume", 0) or 0) <= 0:
            raise ReferencePriceError(f"bitstamp {base}usd has no volume")
        return (float(data["bid"]) + float(data["ask"])) / 2


async def _gemini(session: ClientSession, base: str) -> float:
    url = f"https://api.gemini.com/v1/pubticker/{base.lower()}usd"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"gemini {base}usd status {resp.status}")
        data = await resp.json()
        return (float(data["bid"]) + float(data["ask"])) / 2


async def _bitfinex(session: ClientSession, base: str) -> float:
    url = f"https://api-pub.bitfinex.com/v2/ticker/t{base}USD"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"bitfinex t{base}USD status {resp.status}")
        data = await resp.json()
        # [BID, BID_SIZE, ASK, ASK_SIZE, ...]
        return (float(data[0]) + float(data[2])) / 2


# USDT-quoted venues, rebased at 1.0 like every other USDT hop in the SDK.


async def _binance(session: ClientSession, base: str) -> float:
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"binance {base}USDT status {resp.status}")
        data = await resp.json()
        return float(data["price"])


async def _okx(session: ClientSession, base: str) -> float:
    url = f"https://www.okx.com/api/v5/market/ticker?instId={base}-USDT"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"okx {base}-USDT status {resp.status}")
        data = await resp.json()
        return float(data["data"][0]["last"])


async def _bybit(session: ClientSession, base: str) -> float:
    url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={base}USDT"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"bybit {base}USDT status {resp.status}")
        data = await resp.json()
        return float(data["result"]["list"][0]["lastPrice"])


async def _kucoin(session: ClientSession, base: str) -> float:
    url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={base}-USDT"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise ReferencePriceError(f"kucoin {base}-USDT status {resp.status}")
        data = await resp.json()
        return float(data["data"]["price"])


# Five USD venues and four USDT venues. Independent operators, independent
# APIs; the median tolerates any four of them being down or wrong at once.
DEFAULT_SOURCES: Tuple[Tuple[str, ReferenceSource], ...] = (
    ("coinbase", _coinbase),
    ("kraken", _kraken),
    ("bitstamp", _bitstamp),
    ("gemini", _gemini),
    ("bitfinex", _bitfinex),
    ("binance", _binance),
    ("okx", _okx),
    ("bybit", _bybit),
    ("kucoin", _kucoin),
)


@dataclass
class ReferencePriceProvider:
    """
    Median of independent CEX quotes for <asset>/USD. Venues further than
    `max_deviation` from the median are dropped as outliers, and at least
    `quorum` venues must remain. Never reads the oracle.
    """

    sources: Tuple[Tuple[str, ReferenceSource], ...] = DEFAULT_SOURCES
    quorum: int = 4
    max_deviation: float = 0.02
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
        median = statistics.median(p for _, p in quotes)
        kept = [
            (n, p) for n, p in quotes if abs(p - median) / median <= self.max_deviation
        ]
        dropped = [(n, p) for n, p in quotes if (n, p) not in kept]
        if dropped:
            logger.warning(
                "[Reference] %s/USD: dropping outlier venue(s) %s (median %.6g)",
                ticker,
                dropped,
                median,
            )
        if len(kept) < self.quorum:
            raise ReferencePriceError(
                f"{ticker}/USD: only {len(kept)} venue(s) within "
                f"{self.max_deviation:.0%} of the median {median:.6g}, "
                f"quorum is {self.quorum}: {quotes}"
            )
        return statistics.median(p for _, p in kept)


_default_provider: Optional[ReferencePriceProvider] = None


def get_reference_price_provider() -> ReferencePriceProvider:
    """Process-wide provider so the 10s cache is shared across fetchers."""
    global _default_provider
    if _default_provider is None:
        _default_provider = ReferencePriceProvider()
    return _default_provider
