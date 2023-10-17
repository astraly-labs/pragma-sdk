import collections
import logging
from typing import List, Dict
import time
import aiohttp

from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.utils.typed_data import TypedData

from pragma.core.entry import SpotEntry
from pragma.core.types import AggregationMode

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
    api_url: str

    def sign_publish_message(self, entries: List[SpotEntry]) -> (List[int], int):
        message = build_publish_message(entries)
        hash_ = TypedData.from_dict(message).message_hash(self.account.address)
        sig = self.account.sign_message(message)

        return sig, hash_

    async def publish_data(
        self,
        entries: List[SpotEntry],
    ):
        # Sign message
        sig, _ = self.sign_publish_message(entries)

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

        url = self.api_url + '/v1/data/publish'

        logging.info(f"POST {url}")
        logging.info(f"Headers: {headers}")
        logging.info(f"Body: {body}")

        # Call Pragma API
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Publish successful")
                    return response

                logging.error(f"Status Code: {status_code}")
                logging.error(f"Response Text: {response}")
                logging.error("Unable to POST /v1/data")

        return response

    # pylint: disable=no-self-use
    async def get_spot_data(
        self,
        quote_asset,
        base_asset,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources=None,
    ):
        url = self.api_url + f"/v1/data/{quote_asset}/{base_asset}"

        headers = {}

        logging.info(f"GET {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    logging.info(f"Success: {response}")
                    logging.info("Get Data successful")

                logging.error(f"Status Code: {status_code}")
                logging.error(f"Response Text: {response}")
                logging.error("Unable to GET /v1/data")

        return response
