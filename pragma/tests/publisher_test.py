import os

import pytest
from dotenv import load_dotenv

from pragma.core.client import PragmaClient
from pragma.core.entry import Entry, SpotEntry
from pragma.core.utils import str_to_felt
from pragma.publisher.client import PragmaPublisherClient
from pragma.publisher.fetchers import *
from pragma.publisher.types import PublisherFetchError
from pragma.tests.constants import SAMPLE_ASSETS

ALL_FETCHERS = [
    AscendexFetcher,
    BitstampFetcher,
    CexFetcher,
    CoinbaseFetcher,
    DefillamaFetcher,
    GeminiFetcher,
    OkxFetcher,
]

load_dotenv()


@pytest.mark.asyncio
async def test_publisher_client(pragma_client: PragmaClient, contracts):
    PUBLISHER_NAME = "PRAGMA"
    PUBLISHER_ADDRESS = pragma_client.account_address()

    # Add PRAGMA as Publisher
    await pragma_client.add_publisher(PUBLISHER_NAME, PUBLISHER_ADDRESS)

    publishers = await pragma_client.get_all_publishers()
    assert publishers == [str_to_felt(PUBLISHER_NAME)]

    publisher: PragmaPublisherClient = PragmaPublisherClient.convert_to_publisher(
        pragma_client
    )
    publisher.add_fetcher(CexFetcher(SAMPLE_ASSETS, PUBLISHER_NAME))

    data = await publisher.fetch()
    assert all([isinstance(entry, SpotEntry) for entry in data])

    publisher.add_fetchers(
        [fetcher(SAMPLE_ASSETS, PUBLISHER_NAME) for fetcher in ALL_FETCHERS]
    )

    # Add KaikoFetcher if API KEY is provided
    api_key = os.getenv("KAIKO_API_KEY")
    if api_key:
        publisher.add_fetcher(
            KaikoFetcher(SAMPLE_ASSETS, PUBLISHER_NAME, api_key=api_key)
        )

    data = await publisher.fetch()

    asset_valid_data_type(data, SpotEntry)

    data = publisher.fetch_sync()

    asset_valid_data_type(data, SpotEntry)


def asset_valid_data_type(data, data_type: Entry):
    errors = [entry for entry in data if not isinstance(entry, data_type)]

    if len(errors) > 0:
        print(errors)

    assert all([isinstance(entry, data_type) for entry in data])
