import abc
from typing import List, Optional, Union

from aiohttp import ClientSession

from pragma.onchain.client import PragmaOnChainClient
from pragma.common.types.entry import Entry
from pragma.common.types.pair import Pair
from pragma.onchain.types import Network
from pragma.common.utils import add_sync_methods, str_to_felt
from pragma.common.fetchers.hop_handler import HopHandler
from pragma.common.exceptions import PublisherFetchError


# Abstract base class for all fetchers
@add_sync_methods
class FetcherInterfaceT(abc.ABC):
    pairs: List[Pair]
    publisher: str
    headers: dict
    hop_handler: Optional[HopHandler] = None

    _client = None

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: str = None,
        network: Network = "mainnet",
    ):
        self.pairs = pairs
        self.publisher = publisher
        self.client = self.get_client(network)
        self.headers = {"Accepts": "application/json"}
        if api_key:
            self.headers["X-Api-Key"] = api_key

    @classmethod
    def get_client(cls, network: Network = "mainnet"):
        if cls._client is None:
            cls._client = PragmaOnChainClient(network=network)
        return cls._client

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
