import asyncio
from typing import List

import aiohttp
import http.client
import requests
import os
import json
from pragma.core.client import PragmaClient
from pragma.publisher.types import PublisherInterfaceT
from dotenv import load_dotenv

load_dotenv()

ALLOWED_INTERVALS = ["1m", "15m", "1h"]


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
            data = fetcher.fetch_sync()
            results.extend(data)
        return results


class PragmaAPIClient(PragmaClient):

    api_base_url=os.getenv("PRAGMA_API_BASE_URL"),
    api_key=os.getenv("PRAGMA_API_KEY"),
    
    
    @staticmethod
    def convert_to_publisher(client: PragmaClient):
        client.__class__ = PragmaAPIClient
        return client


    def api_get_ohlc(
        self,
        pair: str,
        timestamp: int,
        interval: str,
        routing: bool,
        aggregation,
        limit: int = 1000,
    ):
        base_asset, quote_asset = pair.split("/")

        # Define the endpoint
        endpoint = f"/aggregation/candlestick/{base_asset}/{quote_asset}"

        # Prepare path parameters
        path_params = {
            "base": base_asset,
            "quote": quote_asset,
            "timestamp": timestamp,
            "interval": interval,
        }

        # Construct the complete URL
        url = f"{self.api_base_url}{endpoint}"

        # Prepare query parameters
        query_params = {"routing": routing, "aggregation": aggregation}

        # Add limit parameter
        query_params["limit"] = limit

        # Prepare headers
        headers = {
            "x-api-key": self.api_key[0],
            "Content-Type": "application/json",
        }

        # Create connection
        conn = http.client.HTTPSConnection("api.dev.pragma.build")

        # Add path parameters to endpoint
        endpoint += "?" + "&".join([f"{key}={path_params[key]}" for key in path_params])

        # Send GET request with headers
        conn.request("GET", endpoint, headers=headers)

        # Get response
        response = conn.getresponse()

        if response.status == 200:
            # Read and parse JSON response
            data = response.read().decode("utf-8")
            return json.loads(data)
        else:
            # Print an error message if the request was unsuccessful
            print(f"Error: {response.status}")
            return None

    def create_entries(self, entries):
        endpoint = "/data/publish"

        headers = {
            "x-api-key": self.api_key[0],
            "Content-Type": "application/json",
        }

        # Convert entries to JSON string
        data = json.dumps({"entries": entries})

        # Create connection
        conn = http.client.HTTPSConnection("api.dev.pragma.build")

        # Send POST request with headers
        conn.request("POST", endpoint, body=data, headers=headers)

        # Get response
        response = conn.getresponse()

        if response.status == 200:
            # Read and parse JSON response
            data = response.read().decode("utf-8")
            return json.loads(data)
        else:
            raise Exception(f"Error {response.status}: {response.reason}")


    def get_entry(self, pair: str, timestamp=None, interval=None, routing=None, aggregation=None):
        base_asset, quote_asset = pair.split("/")

        endpoint = f"/node/v1/data/{base_asset}/{quote_asset}"
        
        # Construct query parameters based on provided arguments
        params = {}
        if timestamp is not None:
            params["timestamp"] = timestamp
        if interval is not None:
            params["interval"] = interval
        if routing is not None:
            params["routing"] = routing
        if aggregation is not None:
            params["aggregation"] = aggregation

        headers = {
            "x-api-key": self.api_key[0],
            "Content-Type": "application/json",
        }

        # Create connection
        conn = http.client.HTTPSConnection("api.dev.pragma.build")

        # Construct URL with parameters
        url = f"{endpoint}?{'&'.join([f'{key}={value}' for key, value in params.items()])}"

        # Send GET request with headers
        conn.request("GET", url, headers=headers)

        # Get response
        response = conn.getresponse()

        if response.status == 200:
            # Read and parse JSON response
            data = response.read().decode("utf-8")
            return json.loads(data)
        else:
            raise Exception(f"Error {response.status}: {response.reason}")

    def get_volatility(self, pair: str, start: int, end: int):
        base_asset, quote_asset = pair.split("/")

        endpoint = f"/node/v1/volatility/{base_asset}/{quote_asset}"

        # Construct query parameters
        params = f"start={start}&end={end}"

        headers = {
            "x-api-key": self.api_key[0],
            "Content-Type": "application/json",
        }

        # Create connection
        conn = http.client.HTTPSConnection(self.api_base_url[0])

        # Construct URL with parameters
        url = f"{endpoint}?{params}"

        # Send GET request with headers
        conn.request("GET", url, headers=headers)

        # Get response
        response = conn.getresponse()

        if response.status == 200:
            # Read and parse JSON response
            data = response.read().decode("utf-8")
            return json.loads(data)
        else:
            raise Exception(f"Error {response.status}: {response.reason}")
