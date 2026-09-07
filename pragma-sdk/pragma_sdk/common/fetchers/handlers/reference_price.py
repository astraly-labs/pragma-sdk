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
from pragma_sdk.common.fetchers.metrics import metrics

logger = get_pragma_sdk_logger()

# Stablecoins are converted at their *measured* USD price, taken from USD
# venues and never from Pragma's oracle. Around the peg that is 0.999..1.001,
# so nothing changes day to day; during a depeg USDT-quoted markets are
# converted correctly instead of being published 7% off "as if 1.0 held".
# USD itself and USDPLUS have no market and stay at 1.0.
#
# Degradation when the peg cannot be measured (too few venues answering):
#   1. last verified value if it is younger than STABLE_MAX_AGE_SECONDS,
#   2. otherwise ReferencePriceError: callers must fail closed for the pairs
#      that need the conversion, and only those.
STABLE_TICKERS = frozenset({"USD", "USDT", "USDC", "DAI", "USDPLUS"})
CHECKED_STABLES = frozenset({"USDT", "USDC", "DAI"})
STABLE_BAND = 0.02  # beyond this we log a depeg, the value is still used
STABLE_MAX_AGE_SECONDS = 300
# Same fallback for ETH/USD, BTC/USD...: a venue hiccup must not drop every
# hopped pair (WSTETH, LBTC, UNIBTC, MRE7BTC) when a value was verified
# moments ago.
REFERENCE_MAX_AGE_SECONDS = 300

# Kraken uses legacy codes for a few assets.
_KRAKEN_ALIASES = {"BTC": "XBT", "DOGE": "XDG"}
_BITFINEX_ALIASES = {"USDT": "UST", "USDC": "UDC"}


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
        if not isinstance(data, dict):
            raise ReferencePriceError(f"bitstamp {base}usd is not a market")
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
    symbol = _BITFINEX_ALIASES.get(base, base)
    url = f"https://api-pub.bitfinex.com/v2/ticker/t{symbol}USD"
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

# Venues quoting the stablecoins themselves in USD, used only for the peg check.
STABLE_CHECK_SOURCES: Tuple[Tuple[str, ReferenceSource], ...] = (
    ("kraken", _kraken),
    ("coinbase", _coinbase),
    ("bitstamp", _bitstamp),
    ("bitfinex", _bitfinex),
)


@dataclass
class ReferencePriceProvider:
    """
    Median of independent CEX quotes for <asset>/USD. Venues further than
    `max_deviation` from the median are dropped as outliers, and at least
    `quorum` venues must remain. Never reads the oracle.
    """

    sources: Tuple[Tuple[str, ReferenceSource], ...] = DEFAULT_SOURCES
    stable_sources: Tuple[Tuple[str, ReferenceSource], ...] = STABLE_CHECK_SOURCES
    quorum: int = 4
    stable_quorum: int = 2
    stable_band: float = STABLE_BAND
    stable_max_age_seconds: float = STABLE_MAX_AGE_SECONDS
    reference_max_age_seconds: float = REFERENCE_MAX_AGE_SECONDS
    max_deviation: float = 0.02
    timeout_seconds: float = 6.0
    cache_ttl_seconds: float = 10.0
    _cache: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    # One lock per ticker: 20+ fetchers ask for ETH/USD at the same instant on
    # a cold cache, one HTTP round must serve them all.
    _locks: Dict[str, asyncio.Lock] = field(default_factory=dict)
    # ticker -> (last verified stable price, monotonic time)
    _last_verified: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    async def get_price(
        self, base: str, quote: str = "USD", session: Optional[ClientSession] = None
    ) -> float:
        """
        Price of one `base` in `quote`: base/USD divided by quote/USD, where
        USD and USDPLUS are 1.0 and every other ticker is measured on venues.
        """
        if session is None:
            async with aiohttp.ClientSession() as own_session:
                return await self.get_price(base, quote, own_session)
        base_usd = await self._usd_price(base, session)
        quote_usd = await self._usd_price(quote, session)
        return base_usd / quote_usd

    async def _usd_price(self, ticker: str, session: ClientSession) -> float:
        if ticker in STABLE_TICKERS and ticker not in CHECKED_STABLES:
            return 1.0
        lock = self._locks.setdefault(ticker, asyncio.Lock())
        async with lock:
            cached = self._cache.get(ticker)
            now = time.monotonic()
            if cached is not None and now - cached[1] < self.cache_ttl_seconds:
                return cached[0]
            if ticker in STABLE_TICKERS:
                price = await self._checked_stable(ticker, session)
            else:
                price = await self._reference_with_fallback(ticker, session)
            self._cache[ticker] = (price, time.monotonic())
            return price

    async def _reference_with_fallback(
        self, ticker: str, session: ClientSession
    ) -> float:
        """
        Venue median for a non-stable ticker; when the quorum cannot be met,
        the last verified value is reused if younger than
        `reference_max_age_seconds`, otherwise ReferencePriceError.
        """
        try:
            price = await self._query_sources(ticker, session)
        except ReferencePriceError as e:
            last = self._last_verified.get(ticker)
            if last is not None:
                value, at = last
                age = time.monotonic() - at
                if age <= self.reference_max_age_seconds:
                    metrics().reference_failure(ticker, "stale_reuse")
                    logger.warning(
                        "[Reference] %s/USD unmeasurable (%s), reusing %.6g verified %.0fs ago",
                        ticker,
                        e,
                        value,
                        age,
                    )
                    return value
            metrics().reference_failure(ticker, "unmeasurable")
            raise
        self._last_verified[ticker] = (price, time.monotonic())
        return price

    async def _checked_stable(self, ticker: str, session: ClientSession) -> float:
        """
        Measured USD price of a stablecoin (USDT, USDC, DAI) from USD venues.

        States, from the most common to the rarest:
          1. measured, within the band: used as is (~1.0),
          2. measured, outside the band: used as is, "depeg" logged,
          3. unmeasurable, last verified value younger than
             `stable_max_age_seconds`: that value is reused, logged,
          4. unmeasurable for longer: ReferencePriceError, callers fail closed
             for the pairs that need the conversion.
        """
        try:
            market = await self._query_sources(
                ticker,
                session,
                sources=self.stable_sources,
                quorum=self.stable_quorum,
            )
        except ReferencePriceError as e:
            last = self._last_verified.get(ticker)
            if last is not None:
                price, at = last
                age = time.monotonic() - at
                if age <= self.stable_max_age_seconds:
                    metrics().reference_failure(ticker, "stale_reuse")
                    logger.warning(
                        "[Reference] %s/USD unmeasurable (%s), reusing %.4f verified %.0fs ago",
                        ticker,
                        e,
                        price,
                        age,
                    )
                    return price
            metrics().reference_failure(ticker, "unmeasurable")
            raise ReferencePriceError(
                f"{ticker}/USD peg unmeasurable and no value verified in the last "
                f"{self.stable_max_age_seconds:.0f}s: {e}"
            ) from e
        metrics().stable_price(ticker, market)
        if abs(market - 1.0) > self.stable_band:
            metrics().reference_failure(ticker, "depeg")
            logger.warning(
                "[Reference] DEPEG: %s/USD measured at %.4f, converting %s-quoted "
                "markets at that rate",
                ticker,
                market,
                ticker,
            )
        self._last_verified[ticker] = (market, time.monotonic())
        return market

    async def _query_sources(
        self,
        ticker: str,
        session: ClientSession,
        sources: Optional[Tuple[Tuple[str, ReferenceSource], ...]] = None,
        quorum: Optional[int] = None,
    ) -> float:
        sources = self.sources if sources is None else sources
        quorum = self.quorum if quorum is None else quorum

        async def one(name: str, source: ReferenceSource) -> Tuple[str, float]:
            async with asyncio.timeout(self.timeout_seconds):
                return name, await source(session, ticker)

        results = await asyncio.gather(
            *(one(name, source) for name, source in sources),
            return_exceptions=True,
        )
        quotes: List[Tuple[str, float]] = []
        for name_source, result in zip(sources, results):
            if isinstance(result, BaseException):
                metrics().reference_venue_failure(ticker, name_source[0])
                # str(TimeoutError()) is empty: always name the exception type
                logger.warning(
                    "[Reference] %s unavailable for %s/USD: %s%s",
                    name_source[0],
                    ticker,
                    type(result).__name__,
                    f": {result}" if str(result) else "",
                )
                continue
            name, price = result
            if price > 0:
                quotes.append((name, price))

        if len(quotes) < quorum:
            raise ReferencePriceError(
                f"{ticker}/USD: only {len(quotes)} reference source(s) answered, "
                f"quorum is {quorum}"
            )
        median = statistics.median(p for _, p in quotes)
        kept = [
            (n, p) for n, p in quotes if abs(p - median) / median <= self.max_deviation
        ]
        dropped = [(n, p) for n, p in quotes if (n, p) not in kept]
        for name, _ in dropped:
            metrics().reference_venue_failure(ticker, name)
        if dropped:
            logger.warning(
                "[Reference] %s/USD: dropping outlier venue(s) %s (median %.6g)",
                ticker,
                dropped,
                median,
            )
        if len(kept) < quorum:
            raise ReferencePriceError(
                f"{ticker}/USD: only {len(kept)} venue(s) within "
                f"{self.max_deviation:.0%} of the median {median:.6g}, "
                f"quorum is {quorum}: {quotes}"
            )
        return statistics.median(p for _, p in kept)


_default_provider: Optional[ReferencePriceProvider] = None


def get_reference_price_provider() -> ReferencePriceProvider:
    """Process-wide provider so the 10s cache is shared across fetchers."""
    global _default_provider
    if _default_provider is None:
        _default_provider = ReferencePriceProvider()
    return _default_provider
