import aiohttp
import json
import time
import hashlib

from typing import Optional, List, Dict, Any, Tuple
from aiohttp import ClientSession
from pydantic.dataclasses import dataclass
from starknet_py.utils.merkle_tree import MerkleTree
from starknet_py.hash.hash_method import HashMethod

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.types import UnixTimestamp
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.entry import Entry, GenericEntry
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.utils import str_to_felt

from pragma_sdk.onchain.constants import DERIBIT_MERKLE_FEED_KEY
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types import Network

logger = get_pragma_sdk_logger()


@dataclass
class DeribitOptionResponse:
    """
    Represents the response returned by the Deribit API for options.
    See:
    https://docs.deribit.com/#public-get_book_summary_by_currency
    """

    mid_price: Optional[float]
    estimated_delivery_price: float
    volume_usd: float
    quote_currency: str
    creation_timestamp: UnixTimestamp
    base_currency: str
    underlying_index: str
    underlying_price: float
    mark_iv: float
    volume: float
    interest_rate: float
    price_change: Optional[float]
    open_interest: float
    ask_price: Optional[float]
    bid_price: Optional[float]
    instrument_name: str
    mark_price: float
    last: Optional[float]
    low: Optional[float]
    high: Optional[float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeribitOptionResponse":
        """
        Converts the complete Deribit JSON response into a DeribitOptionResponse type.
        """
        return cls(
            mid_price=float(data["mid_price"])
            if data.get("mid_price") is not None
            else None,
            estimated_delivery_price=float(data["estimated_delivery_price"]),
            volume_usd=float(data["volume_usd"]),
            quote_currency=str(data["quote_currency"]),
            creation_timestamp=data["creation_timestamp"],
            base_currency=str(data["base_currency"]),
            underlying_index=str(data["underlying_index"]),
            underlying_price=float(data["underlying_price"]),
            mark_iv=float(data["mark_iv"]),
            volume=float(data["volume"]),
            interest_rate=float(data["interest_rate"]),
            price_change=float(data["price_change"])
            if data.get("price_change") is not None
            else None,
            open_interest=float(data["open_interest"]),
            ask_price=float(data["ask_price"])
            if data.get("ask_price") is not None
            else None,
            bid_price=float(data["bid_price"])
            if data.get("bid_price") is not None
            else None,
            instrument_name=str(data["instrument_name"]),
            mark_price=float(data["mark_price"]),
            last=float(data["last"]) if data.get("last") is not None else None,
            low=float(data["low"]) if data.get("low") is not None else None,
            high=float(data["high"]) if data.get("high") is not None else None,
        )

    def extract_strike_price_and_option_type(self) -> Tuple[float, str]:
        """
        Retrieve the strike price and the option type from the instrument name.
        """
        separate_string = self.instrument_name.split("-")
        strike_price = float(separate_string[2])
        option_type = separate_string[3]
        return (strike_price, option_type)


@dataclass
class OptionData:
    instrument_name: str
    base_currency: str
    option_type: str
    creation_timestamp: UnixTimestamp
    current_timestamp: UnixTimestamp
    mark_price: float
    strike_price: float
    volume: float
    volume_usd: float

    @classmethod
    def from_deribit_response(cls, response: DeribitOptionResponse) -> "OptionData":
        strike_price, option_type = response.extract_strike_price_and_option_type()
        current_timestamp = int(time.time())
        return cls(
            instrument_name=response.instrument_name,
            base_currency=response.base_currency,
            option_type=option_type,
            creation_timestamp=response.creation_timestamp,
            current_timestamp=current_timestamp,
            mark_price=response.mark_price * response.underlying_price,
            strike_price=strike_price,
            volume=response.volume,
            volume_usd=response.volume_usd,
        )

    def __hash__(self) -> int:
        hash_input = f"{self.instrument_name}{self.base_currency}{self.current_timestamp}{self.mark_price}"
        return int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)


class DeribitOptionsFetcher(FetcherInterfaceT):
    """
    Deribit fetcher.
    Retrieves all the options data for all available instruments for a set of pairs.

    All the available prices are put in a Merkle tree which is sent in a GenericEntry.
    """

    publisher: str
    pairs: List[Pair]
    headers: Dict[Any, Any]
    _client: PragmaOnChainClient

    REQUIRED_PAIRS = {
        Pair.from_tickers("BTC", "USD"),
        Pair.from_tickers("ETH", "USD"),
    }

    SOURCE: str = "DERIBIT"
    BASE_URL: str = "https://www.deribit.com/api/v2/public"
    ENDPOINT_OPTIONS: str = "get_book_summary_by_currency?currency="
    ENDPOINT_OPTIONS_SUFFIX: str = "&kind=option&expired=false"

    def __init__(
        self,
        pairs: List[Pair],
        publisher: str,
        api_key: Optional[str] = None,
        network: Network = "mainnet",
    ):
        super().__init__(pairs, publisher, api_key, network)
        if set(self.pairs) != self.REQUIRED_PAIRS:
            raise ValueError(
                "Currently, DeribitOptionsFetcher must be used for BTC/USD and ETH/USD only."
            )

    def format_url(self, currency: Currency) -> str:  # type: ignore[override]
        return f"{self.BASE_URL}/{self.ENDPOINT_OPTIONS}{currency.id}{self.ENDPOINT_OPTIONS_SUFFIX}"

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        For every unique base assets in the provided pairs list, fetch all the
        available instruments and their option data.
        They'll be merged in a merkle tree, and we only return the merkle root
        using the GenericEntry type (so we only return one Entry in the final list).
        """
        currencies_options: Dict[str, List[OptionData]] = {}

        unique_currencies = list(set([pair.base_currency for pair in self.pairs]))
        for currency in unique_currencies:
            currencies_options[currency.id] = await self._fetch_options(
                session, currency
            )
        self._currencies_options = currencies_options
        
        merkle_tree = self._build_merkle_tree(currencies_options)

        entry = GenericEntry(
            key=DERIBIT_MERKLE_FEED_KEY,
            value=merkle_tree.root_hash,
            timestamp=int(time.time()),
            source=str_to_felt(self.SOURCE),
            publisher=str_to_felt(self.publisher),
        )
        return [entry]

    def get_currencies_options(self) -> Dict[str, List[OptionData]]:
        return self._currencies_options

    async def _fetch_options(
        self,
        session: ClientSession,
        currency: Currency,
    ) -> List[OptionData]:
        """
        Fetch all options from the Deribit API for a specific currency.
        """
        url = self.format_url(currency)
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    raise PublisherFetchError(
                        f"API request failed with status code {response.status}"
                    )
                data = await response.json()
                self._assert_request_succeeded(data)
                option_responses = [
                    DeribitOptionResponse.from_dict(item) for item in data["result"]
                ]
                return [
                    OptionData.from_deribit_response(response)
                    for response in option_responses
                ]

        except aiohttp.ClientError as e:
            raise PublisherFetchError(f"HTTP request failed: {str(e)}")
        except KeyError as e:
            raise PublisherFetchError(
                f"Deribit options request returned an unexpected data structure: {str(e)}"
            )
        except Exception as e:
            raise PublisherFetchError(f"An unexpected error occurred: {str(e)}")

    def _assert_request_succeeded(self, response: Dict[str, Any]) -> None:
        """
        Raise a PublisherFetchError if the "result" field is not available from
        Deribit response.
        """
        if "result" not in response:
            if "error" in response:
                raise PublisherFetchError(f"API Error: {response['error']}")
            else:
                raise PublisherFetchError("Unexpected API response format")

    def _build_merkle_tree(
        self,
        options: Dict[str, List[OptionData]],
        hash_method: HashMethod = HashMethod.PEDERSEN,
    ) -> MerkleTree:
        """
        Builds and return a MerkleTree from all the available fetched options.
        """
        leaves = []
        for currency, option_data_list in options.items():
            for option_data in option_data_list:
                leaf = hash(option_data)
                leaves.append(leaf)
        leaves.sort()  # Sort the leaves to ensure consistent tree construction
        return MerkleTree(leaves, hash_method)

    async def fetch_pair(  # type: ignore[override]
        self, pair: Pair, session: ClientSession
    ) -> List[Entry] | PublisherFetchError:
        raise NotImplementedError("fetch_pair not needed for Deribit Generic Fetcher.")
