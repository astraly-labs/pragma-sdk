import asyncio
import time
from typing import List, Optional

from aiohttp import ClientSession

from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.onchain.types.types import Network

logger = get_pragma_sdk_logger()

SUPPORTED_ASSETS = [
    ("ETH", "STRK"),
    ("STRK", "USD"),
    ("STRK", "USDT"),
    ("LORDS", "USD"),
    ("LUSD", "USD"),
    ("WBTC", "USD"),
    ("ETH", "LORDS"),
    ("ZEND", "USD"),
    ("ZEND", "USDC"),
    ("ZEND", "USDT"),
    ("ETH", "ZEND"),
    ("NSTR", "USD"),
    ("NSTR", "USDC"),
    ("NSTR", "USDT"),
    ("ETH", "NSTR"),
    ("EKUBO", "USD"),
    ("EKUBO", "USDC"),
]

# Every assets are priced in the Oracle Token.
# To fetch it, we use the Oracle Extension contract.
ORACLE_EXTENSION_CONTRACT = {
    "sepolia": "0x003ccf3ee24638dd5f1a51ceb783e120695f53893f6fd947cc2dcabb3f86dc65",
    "mainnet": "0x005e470ff654d834983a46b8f29dfa99963d5044b993cb7b9c92243a69dab38f",
}

GET_ORACLE_TOKEN_SELECTOR = "get_oracle_token"

# We can then call the `get_prices_in_oracle_tokens` read method to fetch
# the prices of assets. They will be quoted in hte Oracle Token, see above.
PRICE_FETCHER_CONTRACT = {
    "sepolia": "0x002ba1f440e5adb9b90f77d4132b6b1ebc4d6329aa7491f98bfca3dfb8b2a405",
    "mainnet": "0x072b3977b8c7ac971c29745a283bb33600af2ccddeb15934bd0ba315b2c09367",
}

GET_PRICES_SELECTOR = "get_prices"
GET_PRICES_IN_ORACLE_SELECTOR = "get_prices_in_oracle_tokens"


class EkuboFetcher(FetcherInterfaceT):
    SOURCE = "EKUBO"

    oracle_token: Optional[Currency]
    pairs: List[Pair]
    publisher: str
    hop_handler: Optional[HopHandler] = HopHandler(
        hopped_currencies={
            "USD": "USDC",
        }
    )

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: Network = "mainnet",
    ):
        super.__init__(pairs, publisher, api_key, network)
        # TODO: Calls the GET_ORACLE_TOKEN_SELECTOR & store it
        self.oracle_token = self.get_oracle_token()

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetches the data from the fetcher and returns a list of Entry objects.
        """
        entries = []
        for pair in self.pairs:
            if pair.to_tuple() in SUPPORTED_ASSETS:
                entries.append(self.fetch_pair(pair, session))
            else:
                logger.debug(f"Skipping Ekubo for non supported pair: {pair}")

        return list(await asyncio.gather(*entries, return_exceptions=True))  # type: ignore[call-overload]

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        """
        Fetches the data for a specific pair from the fetcher and returns a SpotEntry object.
        """
        raise NotImplementedError("Todo!")

    def format_url(self, pair: Pair) -> str:
        """Formats the URL for the fetcher, used in `fetch_pair` to get the data."""
        ...

    def get_oracle_token(self) -> Currency:
        """
        TODO.
        """
        raise NotImplementedError("Todo!")
