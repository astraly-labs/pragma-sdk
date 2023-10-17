import collections
import logging
from typing import List, Optional
import aiohttp
import time

from deprecated import deprecated
from starknet_py.contract import InvokeResult
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.utils.typed_data import TypedData

from pragma.core.contract import Contract
from pragma.core.entry import FutureEntry, SpotEntry
from pragma.core.types import AggregationMode, DataType, DataTypes, PRAGMA_API_URL
from pragma.core.utils import str_to_felt

logger = logging.getLogger(__name__)

GetDataResponse = collections.namedtuple(
    "GetDataResponse",
    [
        "price",
        "decimals",
        "last_updated_timestamp",
        "num_sources_aggregated",
        "expiration_timestamp",
    ],
)

"""
{'base': 
{'publisher': 88314212732225, 
'source': 5787760245619121969, 'timestamp': 1697147959}, 
'pair_id': 19514442401534788, '
price': 1000, 
'volume': 0}
"""
def build_publish_message(entries: List[SpotEntry]) -> TypedData:
    message = {
        "domain": {"name": "Pragma", "version": "1"},
        "primaryType": "Request",
        "message": {
            "action": "Publish",
            "entries": SpotEntry.serialize_entries(entries),
        },
        "types": {
            "StarkNetDomain": [
                {"name": "name", "type": "felt"},
                {"name": "version", "type": "felt"},
            ],
            "Request": [
                {"name": "action", "type": "felt"},
                {"name": "entries", "type": "Entry*"},
            ],
            "Entry": [
                { "name": "base", "type": "Base" },
                { "name": "pair_id", "type": "felt" },
                { "name": "price", "type": "felt" },
                { "name": "volume", "type": "felt" },
            ],
            "Base": [
                { "name": "publisher", "type": "felt" },
                { "name": "source", "type": "felt" },
                { "name": "timestamp", "type": "felt" },
            ],
        },
    }

    return message


class OffchainMixin:
    client: Client
    account: Account

    def sign_publish_message(self, entries: List[SpotEntry]) -> (List[int], int):
        message = build_publish_message(entries)
        hash = TypedData.from_dict(message).message_hash(self.account.address)
        sig = self.account.sign_message(message)

        return sig, hash

    async def publish_data(
        self,
        entries: List[SpotEntry],
        pagination: Optional[int] = 40,
    ):
        # Sign message
        sig, hash = self.sign_publish_message(entries)

        now = int(time.time())
        expiry = now + 24 * 60 * 60

        # Add headers
        headers: Dict = {
            "PRAGMA-TIMESTAMP": str(now),
            "PRAGMA-SIGNATURE-EXPIRATION": str(expiry),
        }

        body = {
            "signature": [str(s) for s in sig],
            "entries": SpotEntry.offchain_serialize_entries(entries),
        }

        url = PRAGMA_API_URL + '/v1/data/publish'

        logging.info(f"POST {url}")
        logging.info(f"Headers: {headers}")
        logging.info(f"Body: {body}")
        
        print(body)

        # Call Pragma API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                status_code: int = response.status
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Publish successful")
                else:
                    logging.error(f"Status Code: {status_code}")
                    logging.error(f"Response Text: {response}")
                    logging.error("Unable to POST /v1/data")
        
        return response

    async def get_spot(
        self,
        quote_asset,
        base_asset,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources=None,
    ):
        url = PRAGMA_API_URL + f"/v1/data/{quote_asset}/{base_asset}"

        logging.info(f"GET {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Get Data successful")
                    return response["result"]
                else:
                    logging.error(f"Status Code: {status_code}")
                    logging.error(f"Response Text: {response}")
                    logging.error("Unable to GET /v1/data")

        return []