import aiohttp
import time

from typing import Optional, List, Dict, Any
from aiohttp import ClientSession

from starknet_py.hash.hash_method import HashMethod
from starknet_py.utils.merkle_tree import MerkleTree

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.entry import Entry, GenericEntry

from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.onchain.constants import DERIBIT_MERKLE_FEED_KEY
from pragma_sdk.onchain.types import Network

from pragma_sdk.common.fetchers.generic_fetchers.deribit.types import (
    DeribitOptionResponse,
    OptionData,
    CurrenciesOptions,
    LatestData,
)

logger = get_pragma_sdk_logger()


class DeribitOptionsFetcher(FetcherInterfaceT):
    """
    Deribit fetcher.
    Retrieves all the options data for all available instruments for a set of pairs.

    All the available prices are put in a Merkle tree which is sent in a GenericEntry.
    """

    publisher: str
    pairs: List[Pair]
    headers: Dict[Any, Any]
    _latest_data: Optional[LatestData] = None

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
        self._latest_data = None

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        For every unique base assets in the provided pairs list, fetch all the
        available instruments and their option data.
        They'll be merged in a merkle tree, and we only return the merkle root
        using the GenericEntry type (so we only return one Entry in the final list).
        """
        currencies_options: CurrenciesOptions = {}

        unique_currencies = list(set([pair.base_currency for pair in self.pairs]))
        for currency in unique_currencies:
            currencies_options[currency.id] = await self._fetch_options(
                session, currency
            )

        merkle_tree: MerkleTree = self._build_merkle_tree(currencies_options)
        self.latest_data = LatestData(merkle_tree, currencies_options)
        return self._construct(merkle_tree)  # type: ignore[return-value]

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
                    OptionData.from_deribit_response(response, currency.decimals)
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
                leaf = option_data.get_pedersen_hash()
                leaves.append(leaf)
        leaves.sort()  # Sort the leaves to ensure consistent tree construction
        return MerkleTree(leaves, hash_method)

    def _construct(self, merkle_tree: MerkleTree) -> List[GenericEntry]:
        entry = GenericEntry(
            key=DERIBIT_MERKLE_FEED_KEY,
            value=merkle_tree.root_hash,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return [entry]

    @property
    def latest_data(self) -> Optional[LatestData]:
        return self._latest_data

    @latest_data.setter
    def latest_data(self, latest_data: LatestData):
        self._latest_data = latest_data

    def get_latest_built_merkle_tree(self) -> Optional[MerkleTree]:
        """Returns the last built merkle tree used to generate the GenericEntry value."""
        if self._latest_data is None:
            return None
        return self._latest_data.merkle_tree

    def get_latest_fetched_options(self) -> Optional[CurrenciesOptions]:
        """Return the last fetched options used to generate the GenericEntry and the Merkle tree."""
        if self._latest_data is None:
            return None
        return self._latest_data.options

    def format_url(self, currency: Currency) -> str:  # type: ignore[override]
        return f"{self.BASE_URL}/{self.ENDPOINT_OPTIONS}{currency.id}{self.ENDPOINT_OPTIONS_SUFFIX}"

    async def fetch_pair(  # type: ignore[override]
        self, pair: Pair, session: ClientSession
    ) -> List[Entry] | PublisherFetchError:
        raise NotImplementedError("fetch_pair not needed for Deribit Generic Fetcher.")
