import aiohttp
import asyncio
import time

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

logger = get_pragma_sdk_logger()


@dataclass
class DeribitOptionResponse:
    instrument_name: str
    base_currency: str
    creation_timestamp: UnixTimestamp
    mark_iv: float
    mark_price: float
    underlying_price: float
    ask_price: Optional[float]
    bid_price: Optional[float]
    volume: float
    volume_usd: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeribitOptionResponse":
        return cls(
            instrument_name=str(data["instrument_name"]),
            base_currency=str(data["base_currency"]),
            creation_timestamp=data["creation_timestamp"],
            mark_iv=float(data["mark_iv"]),
            mark_price=float(data["mark_price"]),
            underlying_price=float(data["underlying_price"]),
            ask_price=float(data["ask_price"]) if data["ask_price"] else None,
            bid_price=float(data["bid_price"]) if data["bid_price"] else None,
            volume=float(data["volume"]),
            volume_usd=float(data["volume_usd"]),
        )


@dataclass
class OptionData:
    instrument_name: str
    base_currency: str
    option_type: str
    creation_timestamp: UnixTimestamp
    current_timestamp: UnixTimestamp
    mark_iv: float
    mark_price: float
    underlying_price: float
    strike_price: float
    ask_price: Optional[float]
    bid_price: Optional[float]
    volume: float
    volume_usd: float

    def __hash__(self) -> int:
        return hash(
            (
                self.instrument_name,
                self.base_currency,
                self.creation_timestamp,
                self.current_timestamp,
                self.mark_price,
            )
        )


class DeribitGenericFetcher(FetcherInterfaceT):
    """
    Deribit fetcher.
    Retrieves all the options data for all available instruments for a set of pairs.

    All the available prices are put in a Merkle tree which is sent in a GenericEntry.
    """

    publisher: str
    pairs: List[Pair]
    headers: Dict[Any, Any]
    _client: PragmaOnChainClient

    SOURCE: str = "DERIBIT"
    BASE_URL: str = "https://www.deribit.com/api/v2/public"
    ENDPOINT_OPTIONS: str = "get_book_summary_by_currency?currency="
    ENDPOINT_OPTIONS_SUFFIX: str = "&kind=option&expired=false"

    def format_url(self, currency: Currency) -> str:  # type: ignore[override]
        return f"{self.BASE_URL}/{self.ENDPOINT_OPTIONS}{currency.id}{self.ENDPOINT_OPTIONS_SUFFIX}"

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        For every unique base assets in the provided pairs list, fetch all the
        available instruments and their option data.
        They'll be merged in a merkle tree, and we only return the merkle root
        using the GenericEntry type.
        """
        currencies_options: Dict[str, List[OptionData]] = {}

        currencies = list(set([pair.base_currency for pair in self.pairs]))
        for currency in currencies:
            currencies_options[currency.id] = await self._fetch_options(currency)

        merkle_tree = self.build_merkle_tree(currencies_options)

        entry = GenericEntry(
            key=DERIBIT_MERKLE_FEED_KEY,
            value=merkle_tree.root_hash,
            timestamp=int(time.time()),
            source=str_to_felt(self.SOURCE),
            publisher=str_to_felt(self.publisher),
        )
        return [entry]

    def build_merkle_tree(
        self,
        options: Dict[str, List[OptionData]],
        hash_method: HashMethod = HashMethod.PEDERSEN,
    ) -> MerkleTree:
        leaves = []
        for currency, option_data_list in options.items():
            for option_data in option_data_list:
                leaf = abs(hash(option_data)) % (
                    2**251 - 1
                )  # Use a prime number close to 2^251
                leaves.append(leaf)
        # Sort the leaves to ensure consistent tree construction
        leaves.sort()
        return MerkleTree(leaves, hash_method)

    async def _fetch_options(
        self,
        currency: Currency,
    ) -> List[OptionData]:
        """
        Fetch all options from the Deribit API for a specific currency.
        """
        try:
            url = self.format_url(currency)
            current_timestamp = int(time.time())
            async with aiohttp.ClientSession() as session:
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
                    return self._adapt_deribit_response(
                        option_responses, current_timestamp
                    )

        except aiohttp.ClientError as e:
            raise PublisherFetchError(f"HTTP request failed: {str(e)}")
        except KeyError as e:
            raise PublisherFetchError(
                f"Deribit options request returned an unexpected data structure: {str(e)}"
            )
        except Exception as e:
            logger.exception("Unexpected error occurred while fetching option data")
            raise PublisherFetchError(f"An unexpected error occurred: {str(e)}")

    def _adapt_deribit_response(
        self, responses: List[DeribitOptionResponse], current_timestamp: int
    ) -> List[OptionData]:
        """
        Convert the list of options from Deribit to a list of our type OptionData.
        """
        processed_options = []
        for response in responses:
            try:
                strike_price, option_type = self._retrieve_strike_price_and_option_type(
                    response.instrument_name
                )
                option_data = OptionData(
                    instrument_name=response.instrument_name,
                    base_currency=response.base_currency,
                    option_type=option_type,
                    creation_timestamp=response.creation_timestamp,
                    current_timestamp=current_timestamp,
                    mark_iv=response.mark_iv,
                    mark_price=response.mark_price * response.underlying_price,
                    underlying_price=response.underlying_price,
                    strike_price=strike_price,
                    ask_price=response.ask_price * response.underlying_price
                    if response.ask_price
                    else None,
                    bid_price=response.bid_price * response.underlying_price
                    if response.bid_price
                    else None,
                    volume=response.volume,
                    volume_usd=response.volume_usd,
                )
                processed_options.append(option_data)
            except (KeyError, ValueError) as e:
                raise PublisherFetchError(
                    f"Error processing option data for {response.instrument_name}: {str(e)}"
                )
        return processed_options

    def _retrieve_strike_price_and_option_type(
        self, instrument_name: str
    ) -> Tuple[float, str]:
        separate_string = instrument_name.split("-")
        strike_price = float(separate_string[2])
        option_type = separate_string[3]
        return (strike_price, option_type)

    def _assert_request_succeeded(self, response: Dict[str, Any]) -> None:
        if "result" not in response:
            if "error" in response:
                raise PublisherFetchError(f"API Error: {response['error']}")
            else:
                raise PublisherFetchError("Unexpected API response format")

    async def fetch_pair(  # type: ignore[override]
        self, pair: Pair, session: ClientSession
    ) -> List[Entry] | PublisherFetchError:
        raise NotImplementedError("fetch_pair not needed for Deribit Generic Fetcher.")


async def fe(f):
    async with aiohttp.ClientSession() as session:
        d = await f.fetch(session)
    entry = d[0]
    print(entry)
    print(entry.value)


if __name__ == "__main__":
    p = [Pair.from_tickers("BTC", "USD")]
    f = DeribitGenericFetcher(pairs=p, publisher="ADEL")
    asyncio.run(fe(f))
