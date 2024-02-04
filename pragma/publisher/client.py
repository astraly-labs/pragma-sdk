import asyncio
from typing import List

import aiohttp
import requests

from pragma.core.client import PragmaClient
from pragma.publisher.types import PublisherInterfaceT

ALLOWED_INTERVALS = ["1m", "15m", "1h"]


class PragmaAPIClient(PragmaClient):
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
    eapc = PragmaAPIClient('testnet')
    eapc.add_fetchers(fetchers)
    await eapc.fetch()
    eapc.fetch_sync()
    ```

    You can also set a custom timeout duration as followed:
    ```python
    await eapc.fetch(timeout_duration=20) # Denominated in seconds (default=10)
    ```

    """

    def __init__(
        self,
        api_base_url="https://docs.pragmaoracle.com/node/v1",
        api_key="",
    ):
        super().__init__(api_key, api_base_url)
        self.fetchers: List[PublisherInterfaceT] = []

    @staticmethod
    def convert_to_publisher(client: PragmaClient):
        client.__class__ = PragmaAPIClient
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
        endpoint = f"/aggregation/candlestick/{base_asset}/{quote_asset}"  # Replace with the actual endpoint

        # Construct the complete URL
        url = f"{self.base_url}{endpoint}"

        if interval not in ALLOWED_INTERVALS:
            print(
                f"Error: Invalid interval. Allowed values are {', '.join(ALLOWED_INTERVALS)}"
            )
            return None

        # Prepare path parameters
        path_params = {
            "base": base_asset,
            "quote": quote_asset,
            "timestamp": timestamp,
            "interval": interval,
        }
        headers = {
            "Content-Type": "application/json",
        }

        # Prepare query parameters
        query_params = {"routing": routing, "aggregation": aggregation}

        # Make the GET request
        response = requests.get(
            url, params=path_params, json=query_params, headers=headers
        )

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse and return the JSON response
            return response.json()
        else:
            # Print an error message if the request was unsuccessful
            print(f"Error: {response.status_code}")
            return None

    def create_entries(self, entries):
        endpoint = f"{self.api_base_url}/data/publish"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {"entries": entries}

        response = requests.post(endpoint, headers=headers, json=data)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")

    def get_entry(self, pair: str, timestamp: int, interval, routing, aggregation):
        base_asset, quote_asset = pair.split("/")

        if interval not in ALLOWED_INTERVALS:
            print(
                f"Error: Invalid interval. Allowed values are {', '.join(ALLOWED_INTERVALS)}"
            )
            return None

        endpoint = f"{self.api_base_url}/node/v1/data/{base_asset}/{quote_asset}"

        params = {
            "timestamp": timestamp,
            "interval": interval,
            "routing": routing,
            "aggregation": aggregation,
        }

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(endpoint, params=params, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")

    def get_volatility(self, pair: str, start: int, end: int):
        base_asset, quote_asset = pair.split("/")

        endpoint = f"{self.api_base_url}/node/v1/volatility/{base_asset}/{quote_asset}"

        params = {
            "start": start,
            "end": end,
        }

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.get(endpoint, params=params, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")
