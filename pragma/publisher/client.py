import asyncio
import http.client
import json
import os
import time
from typing import Dict, List

import aiohttp
import requests
from dotenv import load_dotenv

from pragma.core.client import PragmaClient
from pragma.core.entry import SpotEntry
from pragma.core.utils import get_cur_from_pair
from pragma.publisher.types import PublisherInterfaceT

load_dotenv()


ALLOWED_INTERVALS = ["1m", "15m", "1h", "2h"]


class EntryResult:
    def __init__(
        self, pair_id, data, num_sources_aggregated=0, timestamp=None, decimals=None
    ):
        self.pair_id = pair_id
        self.data = data
        self.num_sources_aggregated = num_sources_aggregated
        self.timestamp = timestamp
        self.decimals = decimals

    def __str__(self):
        return f"Pair ID: {self.pair_id}, Data: {self.data}, Num Sources Aggregated: {self.num_sources_aggregated}, Timestamp: {self.timestamp}, Decimals: {self.decimals}"

    def assert_attributes_equal(self, expected_dict):
        """
        Asserts that the attributes of the class object are equal to the values in the dictionary.
        """
        for key, value in expected_dict.items():
            if key == "price":
                if getattr(self, "data") != value:
                    return False
            elif getattr(self, key) != value:
                return False
        return True


class PragmaAPIError:
    message: str

    def __init__(self, message: str):
        self.message = message

    def __eq__(self, other):
        return self.message == other.message

    def __repr__(self):
        return self.message

    def serialize(self):
        return self.message


class PragmaPublisherClient(PragmaClient):
    """
    This client extends the pragma client with functionality for fetching from our third party sources.
    It can be used to synchronously or asynchronously fetch assets using the Asset format, ie.

    `{"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 18}`

    More to follow on the standardization of this format.

    The client works by setting up fetchers that are provided the assets to fetch and the publisher name.

    ```python
    cex_fetcher = CexFetcher(PRAGMA_ALL_ASSETS, "pragma_fetcher_test")
    gemini_fetcher = GeminiFetcher(PRAGMA_ALL_ASSETS, "pragma_fetcher_test")
    fetchers = [
        cex_fetcher,
        gemini_fetcher,
    ]
    eapc = PragmaPublisherClient('testnet')
    eapc.add_fetchers(fetchers)
    await eapc.fetch()
    eapc.fetch_sync()
    ```

    You can also set a custom timeout duration as followed:
    ```python
    await eapc.fetch(timeout_duration=20) # Denominated in seconds (default=10)
    ```

    """

    fetchers: List[PublisherInterfaceT] = []

    @staticmethod
    def convert_to_publisher(client: PragmaClient):
        client.__class__ = PragmaPublisherClient
        return client

    def add_fetchers(self, fetchers: List[PublisherInterfaceT]):
        self.fetchers.extend(fetchers)

    def add_fetcher(self, fetcher: PublisherInterfaceT):
        self.fetchers.append(fetcher)

    def update_fetchers(self, fetchers: List[PublisherInterfaceT]):
        self.fetchers = fetchers

    def get_fetchers(self):
        return self.fetchers

    async def fetch(
        self, filter_exceptions=True, return_exceptions=True, timeout_duration=10
    ) -> List[any]:
        tasks = []
        timeout = aiohttp.ClientTimeout(
            total=timeout_duration
        )  # 10 seconds per request
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for fetcher in self.fetchers:
                data = fetcher.fetch(session)
                tasks.append(data)
            result = await asyncio.gather(*tasks, return_exceptions=return_exceptions)
            if filter_exceptions:
                result = [subl for subl in result if not isinstance(subl, Exception)]
            return [val for subl in result for val in subl]

    def fetch_sync(self) -> List[any]:
        results = []
        for fetcher in self.fetchers:
            data = fetcher._fetch_sync()
            results.extend(data)
        return results


class PragmaAPIClient(PragmaClient):
    api_base_ur: str
    api_key: str

    def __init__(
        self,
        api_base_url,
        api_key,
    ):
        self.api_base_url = api_base_url
        self.api_key = api_key

    @staticmethod
    def convert_to_publisher(client: PragmaClient):
        client.__class__ = PragmaAPIClient
        return client

    async def api_get_ohlc(
        self,
        pair: str,
        timestamp: int = None,
        interval: str = None,
        routing: str = None,
        aggregation: str = None,
        limit: int = 1000,
    ):
        base_asset, quote_asset = get_cur_from_pair(pair)

        # Define the endpoint
        endpoint = f"/node/v1/aggregation/candlestick/{base_asset}/{quote_asset}"

        # Prepare path parameters
        path_params = {
            key: value
            for key, value in {
                "timestamp": timestamp,
                "interval": interval,
                "routing": routing,
                "aggregation": aggregation,
            }.items()
            if value is not None
        }

        # Construct the complete URL
        url = f"{self.api_base_url}{endpoint}"
        # Prepare headers
        headers = {
            "x-api-key": self.api_key,
        }
        # Create connection
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, params=path_params
            ) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    print(f"Success: {response}")
                    print("Get Ohlc successful")
                else:
                    print(f"Status Code: {status_code}")
                    return PragmaAPIError(f"Failed to get OHLC data for pair {pair}")

        return EntryResult(pair_id=response["pair_id"], data=response["data"])

    async def create_entries(self, entries):
        endpoint = "/node/v1/data/publish"
        now = int(time.time())
        expiry = now + 24 * 60 * 60

        headers: Dict = {
            "PRAGMA-TIMESTAMP": str(now),
            "PRAGMA-SIGNATURE-EXPIRATION": str(expiry),
            "x-api-key": self.api_key,
        }

        sig, _ = self.sign_publish_message(entries, now, expiry)

        # Convert entries to JSON string
        data = {
            "signature": [str(s) for s in sig],
            "entries": SpotEntry.offchain_serialize_entries(entries),
        }

        url = f"{self.api_base_url}{endpoint}"
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl_context=self.ssl_context)
        ) as session:
            async with session.post(url, headers=headers, json=data) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    print(f"Success: {response}")
                    print("Publish successful")
                    return response
                else:
                    print(f"Status Code: {status_code}")
                    print(f"Response Text: {response}")
                    return PragmaAPIError(f"Unable to POST /v1/data")

    async def get_entry(
        self,
        pair: str,
        timestamp: int = None,
        interval: str = None,
        routing: str = None,
        aggregation: str = None,
    ):
        base_asset, quote_asset = get_cur_from_pair(pair)
        endpoint = f"/node/v1/data/{base_asset}/{quote_asset}"
        url = f"{self.api_base_url}{endpoint}"
        # Construct query parameters based on provided arguments
        params = {
            key: value
            for key, value in {
                "timestamp": timestamp,
                "interval": interval,
                "routing": routing,
                "aggregation": aggregation,
            }.items()
            if value is not None
        }
        headers = {
            "x-api-key": self.api_key,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    print(f"Success: {response}")
                    print("Get Data successful")
                else:
                    print(f"Status Code: {status_code}")
                    print(f"Response Text: {response}")
                    return PragmaAPIError(f"Unable to GET /v1/data for pair {pair}")

        return EntryResult(
            pair_id=response["pair_id"],
            data=response["price"],
            num_sources_aggregated=response["num_sources_aggregated"],
            timestamp=response["timestamp"],
            decimals=response["decimals"],
        )

    async def get_volatility(self, pair: str, start: int, end: int):
        base_asset, quote_asset = get_cur_from_pair(pair)

        endpoint = f"/node/v1/volatility/{base_asset}/{quote_asset}"

        # Construct query parameters
        headers = {
            "x-api-key": self.api_key,
        }

        params = {
            "start": start,
            "end": end,
        }

        # Construct URL with parameters
        url = f"{self.api_base_url}{endpoint}"
        # Send GET request with headers
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                status_code: int = response.status
                response: Dict = await response.json()
                if status_code == 200:
                    print(f"Success: {response}")
                    print("Get Volatility successful")
                else:
                    print(f"Status Code: {status_code}")
                    print(f"Response Text: {response}")
                    raise Exception(f"Unable to GET /v1/volatility for pair {pair} ")

        return EntryResult(pair_id=response["pair_id"], data=response["volatility"])
