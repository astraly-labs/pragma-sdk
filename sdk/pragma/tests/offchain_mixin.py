import time
from typing import Tuple

import pytest
import pytest_asyncio
from starknet_py.utils.typed_data import TypedData

from pragma.onchain.client import PragmaOnChainClient
from pragma.common.types.entry import SpotEntry
from pragma.common.utils import str_to_felt
from pragma.publisher.signer import build_publish_message

PUBLISHER_NAME = "PRAGMA"

ETH_PAIR = str_to_felt("ETH/USD")
BTC_PAIR = str_to_felt("BTC/USD")

SOURCE_1 = "PRAGMA_1"
SOURCE_2 = "PRAGMA_2"
SOURCE_3 = "SOURCE_3"

MOCK_DATA = [
    SpotEntry(
        pair_id=ETH_PAIR,
        source=SOURCE_1,
        publisher=PUBLISHER_NAME,
        price=1000,
        timestamp=int(time.time()),
    ),
    SpotEntry(
        pair_id=ETH_PAIR,
        source=SOURCE_2,
        publisher=PUBLISHER_NAME,
        price=1000,
        timestamp=int(time.time()),
    ),
]

EMPTY_DATA = [
    SpotEntry(
        pair_id="pair_id",
        source="source",
        publisher="publisher",
        price=0,
        timestamp=0,
        volume=0,
    ),
]


@pytest_asyncio.fixture(scope="package", name="pragma_offchain_client")
async def pragma_offchain_client(
    address_and_private_key: Tuple[str, str],
) -> PragmaOnChainClient:
    address, private_key = address_and_private_key

    return PragmaOnChainClient(
        account_contract_address=address,
        account_private_key=private_key,
    )


def test_publish_message():
    msg = build_publish_message(MOCK_DATA)
    hash_ = TypedData.from_dict(msg).message_hash(0)
    print(msg, hash_)


def test_publish_message_empty():
    msg = build_publish_message(EMPTY_DATA)
    hash_ = TypedData.from_dict(msg).message_hash(0)
    print(msg, hash_)


@pytest.mark.asyncio
async def test_publish_api(pragma_offchain_client: PragmaOnChainClient):
    response = await pragma_offchain_client.publish_data(MOCK_DATA)

    assert response.number_entries_created == 2


@pytest.mark.asyncio
async def test_get_data(pragma_offchain_client: PragmaOnChainClient):
    response = await pragma_offchain_client.get_spot_data("ETH", "USD")
    print(response)

    assert response["num_sources_aggregated"] > 0
    assert response["pair_id"] == "ETH/USD"
    assert response["price"] > 0
