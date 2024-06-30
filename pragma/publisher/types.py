import abc
from enum import Enum, unique
from typing import List, Union

from aiohttp import ClientSession

from pragma.core.client import PragmaOnChainClient
from pragma.core.entry import Entry
from pragma.core.types import Pair
from pragma.core.utils import add_sync_methods, str_to_felt


class PublisherFetchError(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def __eq__(self, other):
        return self.message == other.message

    def __repr__(self):
        return self.message

    def serialize(self):
        return self.message


@unique
class Interval(Enum):
    ONE_MINUTE = "1min"
    FIFTEEN_MINUTES = "15min"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"

    def serialize(self):
        return {self.value: None}


# Abstract base class for all fetchers
@add_sync_methods
class FetcherInterfaceT(abc.ABC):
    client: PragmaOnChainClient = PragmaOnChainClient(network="mainnet")
    assets: List[Pair]
    publisher: str
    headers: dict

    def __init__(self, assets: List[Pair], publisher: str, api_key: str = None):
        self.assets = assets
        self.publisher = publisher
        self.headers = {"Accepts": "application/json"}
        if api_key:
            self.headers["X-Api-Key"] = api_key

    @abc.abstractmethod
    async def fetch(self, session: ClientSession) -> List[Entry]: ...

    """
    Fetches the data from the fetcher and returns a list of Entry objects
    """

    @abc.abstractmethod
    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Union[Entry, PublisherFetchError]: ...

    """
    Fetches the data for a specific pair from the fetcher and returns a SpotEntry object
    """

    @abc.abstractmethod
    def format_url(self, pair: Pair) -> str: ...

    """
    Formats the URL for the fetcher, used in `fetch_pair` to get the data
    """

    async def get_stable_price(self, stable_asset: str) -> float:
        """
        Query the PragmaOnChainClient for the price of the stable asset in USD
        e.g get_stable_price("USDT") returns the price of USDT in USD
        """
        usdt_str = str_to_felt(stable_asset + "/USD")
        usdt_entry = await self.client.get_spot(usdt_str)
        return int(usdt_entry.price) / (10 ** int(usdt_entry.decimals))
