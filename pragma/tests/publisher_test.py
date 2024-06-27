from typing import Sequence

import pytest
from dotenv import load_dotenv

from pragma.core.assets import PRAGMA_ALL_ASSETS
from pragma.core.client import PragmaOnChainClient
from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.core.utils import str_to_felt
from pragma.publisher.client import FetcherClient
from pragma.publisher.fetchers import (
    CexFetcher,
    DefillamaFetcher,
    BitstampFetcher,
    CoinbaseFetcher,
    AscendexFetcher,
    OkxFetcher,
    GeckoTerminalFetcher,
)
from pragma.publisher.future_fetchers import OkxFutureFetcher
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import SAMPLE_ASSETS, SAMPLE_FUTURE_ASSETS
from pragma.tests.utils import wait_for_acceptance

ALL_SPOT_FETCHERS = [
    AscendexFetcher,
    BitstampFetcher,
    CexFetcher,
    CoinbaseFetcher,
    DefillamaFetcher,
    OkxFetcher,
    GeckoTerminalFetcher,
]

ALL_FUTURE_FETCHERS = [
    OkxFutureFetcher,
]

ALL_FETCHERS = ALL_SPOT_FETCHERS + ALL_FUTURE_FETCHERS

load_dotenv()

PUBLISHER_NAME = "PRAGMA"
PAGINATION = 40
SOURCES = [
    "ASCENDEX",
    "BITSTAMP",
    "CEX",
    "COINBASE",
    "DEFILLAMA",
    "GEMINI",
    "KAIKO",
    "OKX",
    "BINANCE",
    "BYBIT",
    "GECKOTERMINAL",
]


@pytest.mark.asyncio
async def test_publisher_client_spot(pragma_client: PragmaOnChainClient):
    publisher_address = pragma_client.account_address()
    # Add PRAGMA as Publisher
    await wait_for_acceptance(
        await pragma_client.add_publisher(PUBLISHER_NAME, publisher_address)
    )

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt(PUBLISHER_NAME)]

    await wait_for_acceptance(
        await pragma_client.add_sources_for_publisher(PUBLISHER_NAME, SOURCES)
    )
    sources = await pragma_client.get_publisher_sources(PUBLISHER_NAME)
    assert sources == [str_to_felt(s) for s in SOURCES]

    fetcher = FetcherClient()
    fetcher.update_fetchers(
        [fetcher(SAMPLE_ASSETS, PUBLISHER_NAME) for fetcher in ALL_SPOT_FETCHERS]
    )

    print(f"🧩 Fetchers : {fetcher.get_fetchers()}")

    data = await fetcher.fetch(return_exceptions=False)

    asset_valid_data_type(data, SpotEntry)

    # Publish SPOT data
    print(data)
    await pragma_client.publish_many(data, pagination=PAGINATION, auto_estimate=True)


@pytest.mark.asyncio
async def test_publisher_client_future(pragma_client: PragmaOnChainClient):
    fetcher = FetcherClient()
    fetcher.update_fetchers(
        [
            fetcher(SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME)
            for fetcher in ALL_FUTURE_FETCHERS
        ]
    )

    print(f"🧩 Fetchers : {fetcher.get_fetchers()}")

    data_async: Sequence[Entry] = await fetcher.fetch()

    asset_valid_data_type(data_async, FutureEntry)

    # Publish FUTURE data
    data_list: Sequence[FutureEntry] = [
        d for d in data_async if isinstance(d, FutureEntry)
    ]
    print(data_list)
    await pragma_client.publish_many(
        data_list, pagination=PAGINATION, auto_estimate=True
    )


@pytest.mark.asyncio
async def test_publisher_client_all_assets(pragma_client: PragmaOnChainClient):
    fetcher = FetcherClient()
    fetcher.update_fetchers(
        [fetcher(PRAGMA_ALL_ASSETS, PUBLISHER_NAME) for fetcher in ALL_FETCHERS]
    )

    # Raise exceptions
    data = await fetcher.fetch(return_exceptions=False)

    fetcher_errors = [entry for entry in data if isinstance(entry, PublisherFetchError)]
    print("⚠️ PublisherFetcherErrors : ", fetcher_errors)

    other_errors = [
        entry
        for entry in data
        if not isinstance(entry, PublisherFetchError) and not isinstance(entry, Entry)
    ]
    print("⚠️ Other Errors : ", other_errors)

    # Do not raise exceptions
    data = await fetcher.fetch(return_exceptions=True)

    data = [d for d in data if isinstance(d, Entry)]
    print(data)
    await pragma_client.publish_many(data, pagination=PAGINATION, auto_estimate=True)


def asset_valid_data_type(data: Sequence[Entry], data_type: Entry):
    errors = [entry for entry in data if not isinstance(entry, data_type)]

    if len(errors) > 0:
        print("⚠️ Invalid Data Types :", errors)

    assert all(isinstance(entry, data_type) for entry in data)
