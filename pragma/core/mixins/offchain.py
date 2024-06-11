import collections
import io
import logging
import ssl
import time
from typing import Dict, List

import aiohttp
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.utils.typed_data import TypedData

from pragma.core.entry import Entry, FutureEntry, SpotEntry
from pragma.core.types import AggregationMode
from pragma.core.utils import exclude_none_and_exceptions

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


def build_publish_message(entries: List[Entry]) -> TypedData:
    message = {
        "domain": {"name": "Pragma", "version": "1"},
        "primaryType": "Request",
        "message": {
            "action": "Publish",
            "entries": Entry.serialize_entries(entries),
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
                {"name": "base", "type": "Base"},
                {"name": "pair_id", "type": "felt"},
                {"name": "price", "type": "felt"},
                {"name": "volume", "type": "felt"},
            ],
            "Base": [
                {"name": "publisher", "type": "felt"},
                {"name": "source", "type": "felt"},
                {"name": "timestamp", "type": "felt"},
            ],
        },
    }
    if isinstance(entries[0], FutureEntry):
        message["types"]["Entry"] = message["types"]["Entry"] + [
            {"name": "expiration_timestamp", "type": "felt"},
        ]
    return message


class OffchainMixin:
    client: Client
    account: Account
    api_url: str
    ssl_context: ssl.SSLContext
    api_key: str

    def sign_publish_message(self, entries: List[Entry]) -> (List[int], int):
        """
        Sign a publish message
        """
        message = build_publish_message(entries)
        hash_ = TypedData.from_dict(message).message_hash(self.account.address)
        sig = self.account.sign_message(message)

        return sig, hash_

    def load_ssl_context(self, client_cert, client_key):
        """
        Load SSL context from client cert and key
        """

        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ssl_context.load_cert_chain(
            certfile=io.StringIO(client_cert), keyfile=io.StringIO(client_key)
        )
        self.ssl_context = ssl_context

    async def publish_data(
        self,
        entries: List[Entry],
    ):
        """
        Publish data to PragmAPI

        Args:
            entries (List[Entry]): List of Entry to publish
        """
        # TODO: We sometimes have some Error types in entries, we need to
        # investigate why and don't push them in our entries.
        # Currently, we only exclude them from here.
        entries = exclude_none_and_exceptions(entries)

        spot_entries = [entry for entry in entries if isinstance(entry, SpotEntry)]
        future_entries = [entry for entry in entries if isinstance(entry, FutureEntry)]

        spot_response = self._publish_entries(spot_entries)
        future_response = self._publish_entries(future_entries)

        return spot_response, future_response

    async def _publish_entries(self, entries: List[Entry]):
        # Check if all entries are of the same type
        EntryClass = type(entries[0])
        assert all(isinstance(entry, EntryClass) for entry in entries)

        now = int(time.time())
        expiry = now + 24 * 60 * 60

        # Sign message
        sig, _ = self.sign_publish_message(entries)

        # Add headers
        headers: Dict = {
            "PRAGMA-TIMESTAMP": str(now),
            "PRAGMA-SIGNATURE-EXPIRATION": str(expiry),
            "x-api-key": self.api_key,
        }

        body = {
            "signature": [str(s) for s in sig],
            "entries": EntryClass.offchain_serialize_entries(entries),
        }

        url = self.api_url + "/v1/data/publish"
        if isinstance(entries[0], FutureEntry):
            url += "_future"

        logger.info(f"POST {url}")
        logger.info(f"Headers: {headers}")
        logger.info(f"Body: {body}")

        if self.ssl_context is not None:
            # Call Pragma API
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl_context=self.ssl_context)
            ) as session:
                async with session.post(url, headers=headers, json=body) as response:
                    status_code: int = response.status
                    response: Dict = await response.json()
                    if status_code == 200:
                        logger.info(f"Success: {response}")
                        logger.info("Publish successful")
                        return response

                    logger.error(f"Status Code: {status_code}")
                    logger.error(f"Response Text: {response}")
                    logger.error("Unable to POST /v1/data")
        else:
            # Call Pragma API
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body) as response:
                    status_code: int = response.status
                    response: Dict = await response.json()
                    if status_code == 200:
                        logger.info(f"Success: {response}")
                        logger.info("Publish successful")
                        return response

                    logger.error(f"Status Code: {status_code}")
                    logger.error(f"Response Text: {response}")
                    logger.error("Unable to POST /v1/data")

        return response

    # pylint: disable=no-self-use
    async def get_spot_data(
        self,
        quote_asset,
        base_asset,
        aggregation_mode: AggregationMode = AggregationMode.MEDIAN,
        sources=None,
    ):
        """
        Get spot data from PragmaAPI

        Args:
            quote_asset (str): Quote asset
            base_asset (str): Base asset
            aggregation_mode (AggregationMode): Aggregation mode
            sources (List[str]): List of sources to fetch from
        """
        url = self.api_url + f"/v1/data/{quote_asset}/{base_asset}"

        headers = {
            "x-api-key": self.api_key,
        }

        logger.info(f"GET {url}")

        if self.ssl_context is not None:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl_context=self.ssl_context)
            ) as session:
                async with session.get(url, headers=headers) as response:
                    status_code: int = response.status
                    response: Dict = await response.json()
                    if status_code == 200:
                        logger.info(f"Success: {response}")
                        logger.info("Get Data successful")

                    logger.error(f"Status Code: {status_code}")
                    logger.error(f"Response Text: {response}")
                    logger.error("Unable to GET /v1/data")
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    status_code: int = response.status
                    response: Dict = await response.json()
                    if status_code == 200:
                        logger.info(f"Success: {response}")
                        logger.info("Get Data successful")

                    logger.error(f"Status Code: {status_code}")
                    logger.error(f"Response Text: {response}")
                    logger.error("Unable to GET /v1/data")

        return response
