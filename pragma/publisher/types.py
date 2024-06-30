import abc
from enum import Enum, unique
from typing import Any, List

import aiohttp
from aiohttp import ClientSession

from pragma.core.client import PragmaOnChainClient
from pragma.core.entry import Entry
from pragma.core.types import Pair
from pragma.core.utils import add_sync_methods, str_to_felt


# Abstract base class for all publishers
@add_sync_methods
class FetcherInterfaceT(abc.ABC):
    client: PragmaOnChainClient = PragmaOnChainClient(network="mainnet")

    @abc.abstractmethod
    async def fetch(self, session: ClientSession) -> List[Entry]: ...

    """
    Fetches the data from the publisher and returns a list of Entry objects
    """

    @abc.abstractmethod
    def format_url(self, pair: Pair) -> str: ...

    """
    Formats the URL for the fetcher, used in `_fetch_pair` to get the data
    """

    async def get_stable_price(self, stable_asset):
        """
        Query the PragmaOnChainClient for the price of the stable asset in USD
        """
        usdt_str = str_to_felt(stable_asset + "/USD")
        usdt_entry = await self.client.get_spot(usdt_str)
        return int(usdt_entry.price) / (10 ** int(usdt_entry.decimals))


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
