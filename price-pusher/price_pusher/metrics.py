"""
Prometheus sink for the SDK's fetcher metrics, exposed by the health server
on /metrics. Alert on these, they are the 2026-09-04 incident in numbers:

  pragma_fetcher_entries_total{pair,source}
  pragma_fetcher_entries_rejected_total{pair,source,reason}   zero_price | deviation
  pragma_fetcher_cross_source_deviation{pair,source}          last signed deviation
  pragma_reference_failures_total{ticker,reason}              unmeasurable | stale_reuse | depeg
  pragma_reference_venue_failures_total{ticker,venue}
  pragma_stable_usd_price{ticker}                             measured USDT/USDC/DAI price
  pragma_pusher_pushes_total, pragma_pusher_last_push_timestamp_seconds
"""

import time

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class PrometheusMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        r = self.registry
        self.entries = Counter(
            "pragma_fetcher_entries_total",
            "Entries produced by fetchers",
            ["pair", "source"],
            registry=r,
        )
        self.rejections = Counter(
            "pragma_fetcher_entries_rejected_total",
            "Entries dropped before publication",
            ["pair", "source", "reason"],
            registry=r,
        )
        self.deviations = Gauge(
            "pragma_fetcher_cross_source_deviation",
            "Last deviation of a source from the median of the other sources of its pair",
            ["pair", "source"],
            registry=r,
        )
        self.reference_failures = Counter(
            "pragma_reference_failures_total",
            "Reference price (ETH/USD, USDT/USD...) not established",
            ["ticker", "reason"],
            registry=r,
        )
        self.venue_failures = Counter(
            "pragma_reference_venue_failures_total",
            "Reference venue that failed or was dropped as an outlier",
            ["ticker", "venue"],
            registry=r,
        )
        self.stable_prices = Gauge(
            "pragma_stable_usd_price",
            "Measured USD price of a stablecoin",
            ["ticker"],
            registry=r,
        )
        self.pushes = Counter(
            "pragma_pusher_pushes_total", "Successful on-chain pushes", registry=r
        )
        self.last_push = Gauge(
            "pragma_pusher_last_push_timestamp_seconds",
            "Unix time of the last successful push",
            registry=r,
        )

    # --- FetcherMetrics protocol ---
    def entry(self, pair: str, source: str) -> None:
        self.entries.labels(pair=pair, source=source).inc()

    def rejected(self, pair: str, source: str, reason: str) -> None:
        self.rejections.labels(pair=pair, source=source, reason=reason).inc()

    def deviation(self, pair: str, source: str, deviation: float) -> None:
        self.deviations.labels(pair=pair, source=source).set(deviation)

    def reference_failure(self, ticker: str, reason: str) -> None:
        self.reference_failures.labels(ticker=ticker, reason=reason).inc()

    def reference_venue_failure(self, ticker: str, venue: str) -> None:
        self.venue_failures.labels(ticker=ticker, venue=venue).inc()

    def stable_price(self, ticker: str, price: float) -> None:
        self.stable_prices.labels(ticker=ticker).set(price)

    # --- pusher side ---
    def push_succeeded(self) -> None:
        self.pushes.inc()
        self.last_push.set(time.time())

    def exposition(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
