"""
Every fetcher used to build its own PragmaOnChainClient, and building one
parses three contract ABIs (seconds of CPU). With dozens of fetchers that was
minutes of silent, blocking startup in the price pusher.
"""

from unittest import mock

from pragma_sdk.common.fetchers import interface
from pragma_sdk.common.fetchers.fetchers import BitstampFetcher, OkxFetcher
from pragma_sdk.common.types.pair import Pair


def test_fetchers_share_one_client_per_network():
    pairs = [Pair.from_tickers("BTC", "USD")]
    with (
        mock.patch.dict(interface._shared_clients, {}, clear=True),
        mock.patch.object(
            interface, "PragmaOnChainClient", side_effect=lambda network: object()
        ) as ctor,
    ):
        a = BitstampFetcher(pairs, "TEST")
        b = OkxFetcher(pairs, "TEST")
        c = OkxFetcher(pairs, "TEST", network="sepolia")

    assert a.client is b.client
    assert c.client is not a.client
    assert ctor.call_count == 2
