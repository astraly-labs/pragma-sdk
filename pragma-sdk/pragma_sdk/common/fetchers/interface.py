import abc
from typing import List, Optional, Dict, Any

from aiohttp import ClientSession

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.onchain.types import Network
from pragma_sdk.common.utils import add_sync_methods
from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.fetchers.handlers.reference_price import (
    ReferencePriceError,
    get_reference_price_provider,
)
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

    async def get_stable_price(self, stable_asset: str) -> Optional[float]:
        """
        Conversion factor for hopped pairs (X/USDT -> X/USD): the measured
        <stable>/USD price from independent USD venues, ~1.0 around the peg
        and the real rate during a depeg. None when it cannot be established
        (see reference_price.py): callers must then fail closed for hopped
        pairs only and keep publishing direct pairs.

        Never read from our own oracle: on 2026-09-04 USDT/USD went to 2.04
        with two valid sources and every USDT-quoted CEX price was published
        at -51%.
        """
        try:
            return await get_reference_price_provider().get_price(stable_asset, "USD")
        except ReferencePriceError as e:
            logger.warning(
                "[⚠️ Fetcher] %s: no %s/USD conversion factor, hopped pairs "
                "will not be published: %s",
                self.__class__.__name__,
                stable_asset,
                e,
            )
            return None

    # A quote whose bid/ask spread is wider than this comes from a market too
    # thin to be a price (Huobi STRK/USDT sat at 2-3% and printed -8%).
    MAX_BID_ASK_SPREAD: float = 0.02

    def reject_wide_spread(
        self, pair: Pair, bid: float, ask: float
    ) -> Optional[PublisherFetchError]:
        if bid <= 0 or ask <= 0 or ask < bid:
            return PublisherFetchError(
                f"No usable order book for {pair} from {self.SOURCE}: "
                f"bid={bid} ask={ask}"
            )
        spread = (ask - bid) / ((ask + bid) / 2)
        if spread > self.MAX_BID_ASK_SPREAD:
            return PublisherFetchError(
                f"{self.SOURCE} {pair}: bid/ask spread {spread:.2%} above "
                f"{self.MAX_BID_ASK_SPREAD:.0%}, market too thin"
            )
        return None

    @staticmethod
    def rebase_factor(
        pair: Pair, hopped: bool, factor: Optional[float], stable: str = "USDT"
    ) -> float | PublisherFetchError:
        """
        Factor to apply to a fetched price: 1 for a direct pair (USDT/USD is
        already in USD), the stable's USD price for a hopped pair, and an
        error when a hopped pair has no factor.
        """
        if not hopped:
            return 1.0
        if factor is None:
            return PublisherFetchError(
                f"No verified {stable}/USD conversion for {pair}, not publishing"
            )
        return factor
