"""
Cross-source guard in FetcherClient: with four or more sources on a pair, an
entry more than 10% off the median of the others is replaced by an error;
below that it is only logged; with two or three sources nothing is rejected.
"""

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.types.entry import SpotEntry


def _entries(pair: str, prices, sources=None):
    sources = sources or [f"S{i}" for i in range(len(prices))]
    return [
        SpotEntry(pair, int(p * 1e8), 12345, s, "PUB") for p, s in zip(prices, sources)
    ]


def _prices(values):
    return [v.price / 1e8 if isinstance(v, SpotEntry) else v for v in values]


def test_outlier_is_rejected_with_four_sources():
    values = _entries("BTC/USD", [80000, 80010, 79990, 88800], ["A", "B", "C", "HUOBI"])
    out = FetcherClient._guard_cross_source_deviation(values)
    assert [type(v) for v in out] == [SpotEntry] * 3 + [PublisherFetchError]
    assert "HUOBI" in str(out[3]) and "+11.0%" in str(out[3])


def test_small_deviation_is_only_logged():
    values = _entries("BTC/USD", [80000, 80010, 79990, 84800])  # +6%
    out = FetcherClient._guard_cross_source_deviation(values)
    assert all(isinstance(v, SpotEntry) for v in out)


def test_three_sources_are_never_rejected():
    values = _entries("LORDS/USD", [0.00234, 0.00235, 0.00207])  # -12% outlier
    out = FetcherClient._guard_cross_source_deviation(values)
    assert all(isinstance(v, SpotEntry) for v in out)


def test_two_against_two_rejects_nobody():
    # no camp has three sources: nobody can tell which side is right
    values = _entries("BTC/USD", [80000, 80010, 90000, 90100])
    out = FetcherClient._guard_cross_source_deviation(values)
    assert all(isinstance(v, SpotEntry) for v in out)


def test_three_against_two_rejects_the_minority():
    values = _entries("BTC/USD", [80000, 80010, 79990, 90000, 90100])
    out = FetcherClient._guard_cross_source_deviation(values)
    assert [isinstance(v, SpotEntry) for v in out] == [True, True, True, False, False]


def test_two_sources_are_never_rejected():
    values = _entries("NSTR/USD", [0.0061, 0.0080])
    out = FetcherClient._guard_cross_source_deviation(values)
    assert all(isinstance(v, SpotEntry) for v in out)


def test_pairs_are_judged_independently_and_errors_pass_through():
    values = (
        _entries("BTC/USD", [80000, 80010, 79990, 88800])
        + _entries("ETH/USD", [2500, 2501, 2499, 2502])
        + [PublisherFetchError("upstream")]
    )
    out = FetcherClient._guard_cross_source_deviation(values)
    assert isinstance(out[3], PublisherFetchError)
    assert all(isinstance(v, SpotEntry) for v in out[4:8])
    assert isinstance(out[8], PublisherFetchError) and str(out[8]) == "upstream"
