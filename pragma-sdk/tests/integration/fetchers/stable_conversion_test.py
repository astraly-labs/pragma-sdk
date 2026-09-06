"""
Stablecoin conversion during a depeg.

USDT-quoted venues are converted with the *measured* USDT/USD price. During a
depeg (USDT at 0.93) every hopped pair must still be published, at the right
USD value; direct pairs (USDT/USD itself) are never rebased; and when no
factor can be established, only the hopped pairs are dropped.
"""

import aiohttp
import pytest

from unittest import mock
from aioresponses import aioresponses

from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.fetchers import OkxFetcher, BitstampFetcher
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair

from tests.integration.fixtures.fetchers import get_mock_data
from tests.integration.constants import SAMPLE_PAIRS
from tests.integration.fetchers.fetcher_configs import (
    FETCHER_CONFIGS,
    PUBLISHER_NAME,
)
from tests.integration.utils import are_entries_list_equal

DEPEG = 0.93


def _hops_via_usdt(fetcher) -> bool:
    handler = getattr(fetcher, "hop_handler", None)
    return bool(handler and handler.hopped_currencies.get("USD") == "USDT")


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fetcher_config", list(FETCHER_CONFIGS.values()), ids=list(FETCHER_CONFIGS)
)
async def test_every_fetcher_keeps_publishing_during_a_usdt_depeg(
    fetcher_config, stub_reference_provider
):
    stub_reference_provider.PRICES = {**stub_reference_provider.PRICES, "USDT": DEPEG}
    mock_data = get_mock_data(fetcher_config)
    fetcher = fetcher_config["fetcher_class"](SAMPLE_PAIRS, PUBLISHER_NAME)

    with aioresponses() as m:
        for pair in SAMPLE_PAIRS:
            base = pair.base_currency.id
            if fetcher.hop_handler is not None:
                pair = fetcher.hop_handler.get_hop_pair(pair) or pair
            m.get(fetcher.format_url(pair=pair), status=200, payload=mock_data[base])
        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

    factor = DEPEG if _hops_via_usdt(fetcher) else 1.0
    expected = [
        SpotEntry(
            e.pair_id,
            int(e.price * factor) if factor != 1.0 else e.price,
            e.base.timestamp,
            e.base.source,
            e.base.publisher,
            volume=e.volume,
        )
        for e in fetcher_config["expected_result"]
    ]
    # Same number of entries as on a normal day: a depeg must not thin the
    # medians (the 2026-09-04 failure mode).
    assert len([r for r in result if isinstance(r, SpotEntry)]) == len(expected)
    assert are_entries_list_equal(result, expected)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_direct_stable_pair_is_never_rebased(stub_reference_provider):
    stub_reference_provider.PRICES = {**stub_reference_provider.PRICES, "USDT": DEPEG}
    usdt_usd = Pair.from_tickers("USDT", "USD")
    fetcher = OkxFetcher([usdt_usd], PUBLISHER_NAME)
    payload = {"code": "0", "msg": "", "data": [{"last": "0.9300", "volCcy24h": "10"}]}

    with aioresponses() as m:
        m.get(fetcher.format_url(pair=usdt_usd), status=200, payload=payload)
        async with aiohttp.ClientSession() as session:
            [entry] = await fetcher.fetch(session)

    assert isinstance(entry, SpotEntry)
    assert entry.price == int(0.93 * 10 ** usdt_usd.decimals())  # not 0.93 * 0.93


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_without_a_factor_only_hopped_pairs_are_dropped(stub_reference_provider):
    stub_reference_provider.PRICES = {
        k: v for k, v in stub_reference_provider.PRICES.items() if k != "USDT"
    }
    btc_usd, usdt_usd = (
        Pair.from_tickers("BTC", "USD"),
        Pair.from_tickers("USDT", "USD"),
    )
    fetcher = OkxFetcher([btc_usd, usdt_usd], PUBLISHER_NAME)
    payload = {"code": "0", "msg": "", "data": [{"last": "80000", "volCcy24h": "10"}]}

    with aioresponses() as m:
        m.get(
            fetcher.format_url(pair=Pair.from_tickers("BTC", "USDT")), payload=payload
        )
        m.get(fetcher.format_url(pair=usdt_usd), payload=payload)
        async with aiohttp.ClientSession() as session:
            result = await fetcher.fetch(session)

    by_type = {type(r): r for r in result}
    assert "No verified USDT/USD conversion for BTC/USD" in str(
        by_type[PublisherFetchError]
    )
    assert by_type[SpotEntry].pair_id == usdt_usd.id


def test_fetcher_client_lists_are_per_instance():
    a, b = FetcherClient(), FetcherClient()
    a.add_fetcher(BitstampFetcher([Pair.from_tickers("BTC", "USD")], PUBLISHER_NAME))
    assert len(a.fetchers) == 1
    assert b.fetchers == []
