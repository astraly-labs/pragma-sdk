import time
from typing import Tuple
from urllib.parse import urlparse

import pytest
import pytest_asyncio

from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import str_to_felt
from pragma.core.mixins.offchain import build_publish_message
from starknet_py.utils.typed_data import TypedData

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

@pytest_asyncio.fixture(scope="package", name="pragma_offchain_client")
async def pragma_offchain_client(
    address_and_private_key: Tuple[str, str],
) -> PragmaClient:
    address, private_key = address_and_private_key

    return PragmaClient(
        account_contract_address=address,
        account_private_key=private_key,
    )

def test_publish_message():
    msg = build_publish_message(MOCK_DATA)
    hash = TypedData.from_dict(msg).message_hash(0)
    print(msg, hash)


@pytest.mark.asyncio
async def test_publish_api(pragma_offchain_client: PragmaClient):
    response = await pragma_offchain_client.publish_data(MOCK_DATA)

    assert response.status == 200