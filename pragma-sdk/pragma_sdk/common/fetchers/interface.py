import abc
from typing import List, Optional, Dict, Any

from aiohttp import ClientSession

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.onchain.types import Network
from pragma_sdk.common.utils import add_sync_methods, str_to_felt
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.logging import get_pragma_sdk_logger

logger = get_pragma_sdk_logger()


# TODO(akhercha): FetcherInterfaceT should take as parameter the client instead of creating it
# Abstract base class for all fetchers
@add_sync_methods
class FetcherInterfaceT(abc.ABC):
    pairs: List[Pair]
    publisher: str
    headers: Dict[Any, Any]
    hop_handler: Optional[HopHandler] = None

    _client = None

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: Network = "mainnet",
    ):
        self.pairs = pairs
        self.publisher = publisher
        self.client = self.get_client(network)
        self.headers = {"Accepts": "application/json"}
        if api_key:
            self.headers["X-Api-Key"] = api_key

    @abc.abstractmethod
    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetches the data from the fetcher and returns a list of Entry objects.
        """
        ...

    @abc.abstractmethod
    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        """
        Fetches the data for a specific pair from the fetcher and returns a SpotEntry object.
        """
        ...

    @abc.abstractmethod
    def format_url(self, pair: Pair) -> str:
        """Formats the URL for the fetcher, used in `fetch_pair` to get the data."""
        ...

    def get_client(self, network: Network = "mainnet") -> PragmaOnChainClient:
        if self._client is None:
            self._client = PragmaOnChainClient(network=network)
        return self._client

    async def get_stable_price(self, stable_asset: str) -> float:
        """
        Query the PragmaOnChainClient for the price of the stable asset in USD
        e.g get_stable_price("USDT") returns the price of USDT in USD

        This is only used to rebase hopped pairs (e.g. X/USDT -> X/USD). If the
        on-chain call fails (RPC down, rate-limited, ...), we must NOT let the
        whole fetcher crash: we degrade gracefully to 1.0 so that direct fiat
        pairs (e.g. USDT/USD, which ignore this value) and the other pairs still
        publish. The induced error on hopped pairs is bounded by the stablecoin
        depeg (~0.06% while USDT≈1).
        """

        pair_str = stable_asset + "/USD"
        try:
            entry = await self.client.get_spot(str_to_felt(pair_str))
            return int(entry.price) / int(10 ** int(entry.decimals))
        except Exception as e:
            logger.warning(
                "[⚠️ Fetcher] On-chain %s price unavailable (%s); "
                "falling back to 1.0 for stable rebasing.",
                pair_str,
                type(e).__name__,
            )
            return 1.0
