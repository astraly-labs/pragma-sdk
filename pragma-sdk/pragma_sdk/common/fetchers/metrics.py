"""
Metrics hook for the fetching pipeline.

The SDK does not depend on a metrics library: it emits events to a sink that
the host process installs (`set_metrics_sink`). The price-pusher installs a
Prometheus sink and exposes it on /metrics; anything else gets the no-op
default. Every event here is something an operator should be able to alert
on, because each one was a silent log line during the 2026-09-04 incident.
"""

from __future__ import annotations

from typing import Optional, Protocol


class FetcherMetrics(Protocol):
    def entry(self, pair: str, source: str) -> None:
        """One entry produced by a fetcher, before publication."""

    def rejected(self, pair: str, source: str, reason: str) -> None:
        """One entry dropped before publication: zero_price, deviation, ..."""

    def deviation(self, pair: str, source: str, deviation: float) -> None:
        """Signed deviation of an entry from the median of the other sources."""

    def reference_failure(self, ticker: str, reason: str) -> None:
        """A reference price (ETH/USD, USDT/USD, ...) could not be established."""

    def reference_venue_failure(self, ticker: str, venue: str) -> None:
        """One reference venue did not answer or was dropped as an outlier."""

    def stable_price(self, ticker: str, price: float) -> None:
        """Measured USD price of a stablecoin used for conversion."""


class NullMetrics:
    def entry(self, pair: str, source: str) -> None:
        pass

    def rejected(self, pair: str, source: str, reason: str) -> None:
        pass

    def deviation(self, pair: str, source: str, deviation: float) -> None:
        pass

    def reference_failure(self, ticker: str, reason: str) -> None:
        pass

    def reference_venue_failure(self, ticker: str, venue: str) -> None:
        pass

    def stable_price(self, ticker: str, price: float) -> None:
        pass


_sink: FetcherMetrics = NullMetrics()


def set_metrics_sink(sink: Optional[FetcherMetrics]) -> None:
    global _sink
    _sink = sink if sink is not None else NullMetrics()


def metrics() -> FetcherMetrics:
    return _sink
