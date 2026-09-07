"""The SDK emits fetcher events to an installable sink; default is a no-op."""

import pytest

from pragma_sdk.common.fetchers import metrics as m
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.types.entry import SpotEntry


class Recording:
    def __init__(self):
        self.events = []

    def entry(self, pair, source):
        self.events.append(("entry", pair, source))

    def rejected(self, pair, source, reason):
        self.events.append(("rejected", pair, source, reason))

    def deviation(self, pair, source, deviation):
        self.events.append(("deviation", pair, source, round(deviation, 3)))

    def reference_failure(self, ticker, reason):
        self.events.append(("reference_failure", ticker, reason))

    def reference_venue_failure(self, ticker, venue):
        self.events.append(("venue_failure", ticker, venue))

    def stable_price(self, ticker, price):
        self.events.append(("stable_price", ticker, price))


@pytest.fixture
def sink():
    rec = Recording()
    m.set_metrics_sink(rec)
    yield rec
    m.set_metrics_sink(None)


def test_default_sink_is_a_no_op():
    m.set_metrics_sink(None)
    assert isinstance(m.metrics(), m.NullMetrics)
    m.metrics().rejected("BTC/USD", "X", "zero_price")  # must not raise


def test_guard_events_reach_the_sink(sink):
    values = [
        SpotEntry("BTC/USD", int(p * 1e8), 12345, s, "PUB")
        for p, s in [(80000, "A"), (80010, "B"), (79990, "C"), (88800, "HUOBI")]
    ]
    FetcherClient._guard_cross_source_deviation(values)
    FetcherClient._reject_zero_price(SpotEntry("DAI/USD", 0, 12345, "BINANCE", "PUB"))
    kinds = [e[0] for e in sink.events]
    assert kinds.count("deviation") == 4
    assert ("rejected", "BTC/USD", "HUOBI", "deviation") in sink.events
    assert ("rejected", "DAI/USD", "BINANCE", "zero_price") in sink.events
