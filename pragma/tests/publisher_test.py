import os
import traceback
from copy import deepcopy

import pytest
from dotenv import load_dotenv

from pragma.core.assets import PRAGMA_ALL_ASSETS
from pragma.core.client import PragmaClient
from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.core.utils import str_to_felt
from pragma.publisher.client import PragmaPublisherClient
from pragma.publisher.fetchers import *
from pragma.publisher.future_fetchers import *
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import SAMPLE_ASSETS, SAMPLE_FUTURE_ASSETS

ALL_SPOT_FETCHERS = [
    AscendexFetcher,
    BitstampFetcher,
    CexFetcher,
    CoinbaseFetcher,
    DefillamaFetcher,
    # GeminiFetcher,
    OkxFetcher,
]

ALL_FUTURE_FETCHERS = [
    OkxFutureFetcher,
    # BinanceFutureFetcher,
    # ByBitFutureFetcher
]

ALL_FETCHERS = ALL_SPOT_FETCHERS + ALL_FUTURE_FETCHERS

load_dotenv()

PUBLISHER_NAME = "PRAGMA"

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
]


@pytest.mark.asyncio
async def test_publisher_client_spot(pragma_client: PragmaClient, contracts):
    PUBLISHER_ADDRESS = pragma_client.account_address()

    # Add PRAGMA as Publisher
    await pragma_client.add_publisher(PUBLISHER_NAME, PUBLISHER_ADDRESS)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt(PUBLISHER_NAME)]

    await pragma_client.add_sources_for_publisher(PUBLISHER_NAME, SOURCES)
    sources = await pragma_client.get_publisher_sources(PUBLISHER_NAME)
    assert sources == [str_to_felt(s) for s in SOURCES]

    publisher: PragmaPublisherClient = PragmaPublisherClient.convert_to_publisher(
        pragma_client
    )

    publisher.update_fetchers(
        [fetcher(SAMPLE_ASSETS, PUBLISHER_NAME) for fetcher in ALL_SPOT_FETCHERS]
    )

    print(f"🧩 Fetchers : ", publisher.get_fetchers())

    # Add KaikoFetcher if API KEY is provided
    api_key = os.getenv("KAIKO_API_KEY")
    if api_key:
        publisher.add_fetcher(
            KaikoFetcher(SAMPLE_ASSETS, PUBLISHER_NAME, api_key=api_key)
        )

    data = await publisher.fetch(return_exceptions=False)

    asset_valid_data_type(data, SpotEntry)

    data = publisher.fetch_sync()

    asset_valid_data_type(data, SpotEntry)

    # Publish SPOT data
    print(data)
    await publisher.publish_many(data, pagination=10)


@pytest.mark.asyncio
async def test_publisher_client_future(pragma_client: PragmaClient, contracts):
    PUBLISHER_ADDRESS = pragma_client.account_address()

    publisher: PragmaPublisherClient = PragmaPublisherClient.convert_to_publisher(
        pragma_client
    )

    publisher.update_fetchers(
        [
            fetcher(SAMPLE_FUTURE_ASSETS, PUBLISHER_NAME)
            for fetcher in ALL_FUTURE_FETCHERS
        ]
    )

    print(f"🧩 Fetchers : ", publisher.get_fetchers())

    data = await publisher.fetch()

    asset_valid_data_type(data, FutureEntry)

    data = publisher.fetch_sync()

    asset_valid_data_type(data, FutureEntry)

    # Publish FUTURE data
    data = [d for d in data if isinstance(d, FutureEntry)]
    await publisher.publish_many(data)


@pytest.mark.asyncio
async def test_publisher_client_all_assets(pragma_client: PragmaClient, contracts):
    PUBLISHER_ADDRESS = pragma_client.account_address()

    publisher: PragmaPublisherClient = PragmaPublisherClient.convert_to_publisher(
        pragma_client
    )

    publisher.update_fetchers(
        [fetcher(PRAGMA_ALL_ASSETS, PUBLISHER_NAME) for fetcher in ALL_FETCHERS]
    )

    # Add KaikoFetcher if API KEY is provided
    api_key = os.getenv("KAIKO_API_KEY")
    if api_key:
        publisher.add_fetcher(
            KaikoFetcher(PRAGMA_ALL_ASSETS, PUBLISHER_NAME, api_key=api_key)
        )

    # Raise exceptions
    data = await publisher.fetch(return_exceptions=False)

    fetcher_errors = [entry for entry in data if isinstance(entry, PublisherFetchError)]
    print("⚠️ PublisherFetcherErrors : ", fetcher_errors)

    other_errors = [
        entry
        for entry in data
        if not isinstance(entry, PublisherFetchError) and not isinstance(entry, Entry)
    ]
    print("⚠️ Other Errors : ", other_errors)

    # Do not raise exceptions
    data = await publisher.fetch(return_exceptions=True)


def asset_valid_data_type(data, data_type: Entry):
    errors = [entry for entry in data if not isinstance(entry, data_type)]

    if len(errors) > 0:
        print("⚠️ Invalid Data Types :", errors)

    assert all([isinstance(entry, data_type) for entry in data])
