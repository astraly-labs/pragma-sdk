"""
get_prices(
    quote=USDC,
    base=[all_pairs]
)
price = U256(low=880723287046076025781423701156, high=0)
usd = (price / (2**128)) * (10**DECIMALS)
"""

import time

from typing import List, Optional, Dict, Tuple
from enum import IntEnum
from aiohttp import ClientSession

from starknet_py.net.client_models import Call
from starknet_py.hash.selector import get_selector_from_name

from pragma_sdk.common.fetchers.handlers.hop_handler import HopHandler
from pragma_sdk.common.types.entry import Entry, SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.exceptions import PublisherFetchError
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.common.utils import u256_parts_to_int

from pragma_sdk.onchain.types.types import Network

logger = get_pragma_sdk_logger()

PRICE_FETCHER_CONTRACT = {
    "sepolia": "0x002ba1f440e5adb9b90f77d4132b6b1ebc4d6329aa7491f98bfca3dfb8b2a405",
    "mainnet": "0x072b3977b8c7ac971c29745a283bb33600af2ccddeb15934bd0ba315b2c09367",
}

GET_PRICES_SELECTOR = get_selector_from_name("get_prices")
PERIOD = 3600
MIN_TOKENS = 0


class EkuboStatus(IntEnum):
    NOT_INITIALIZED = 0
    INSUFFICIENT_LIQUIDITY = 1
    PERIOD_TOO_LONG = 2
    PRICE_AVAILABLE = 3


class EkuboFetcher(FetcherInterfaceT):
    SOURCE: str = "EKUBO"

    pairs: List[Pair]
    publisher: str
    price_fetcher_contract: int
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
        self.price_fetcher_contract = int(PRICE_FETCHER_CONTRACT[network], 16)
        super().__init__(pairs, publisher, api_key, network)

    async def fetch(
        self, session: ClientSession
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetches the data from the fetcher and returns a list of Entry objects.
        """
        pairs = [self.hop_handler.get_hop_pair(pair) or pair for pair in self.pairs]
        groupped_pairs = self._group_pairs_by_quote(pairs)
        entries = []
        for quote_currency, base_currencies in groupped_pairs.items():
            response = await self._call_get_prices(quote_currency, base_currencies)
            print(response)
            new_entries = self._parse_response_into_entries(
                quote_currency, base_currencies, response
            )
            entries.extend(new_entries)
        return entries  # type: ignore[call-overload]

    async def _call_get_prices(
        self, quote: Currency, bases: List[Currency]
    ) -> List[int]:
        """
        Calls the get_prices function from the Price Fetcher contract and returns
        the response.
        """
        rpc_client = self.get_client().full_node_client
        call = Call(
            to_addr=self.price_fetcher_contract,
            selector=GET_PRICES_SELECTOR,
            calldata=[
                quote.starknet_address,
                len(bases),
                *[c.starknet_address for c in bases],
                PERIOD,
                MIN_TOKENS,
            ],
        )
        response = await rpc_client.call_contract(
            call=call,
            block_hash="pending",
        )
        return response

    def _parse_response_into_entries(
        self, quote: Currency, bases: List[Currency], res: List[int]
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Parse response data into a list of entries or errors.
        First element is the number of responses.
        Following elements are either:
            - Status (0: NotInitialized, 1: InsufficientLiquidity, 2: PeriodTooLong, 3: Price)
            - If status is 3 (PRICE_AVAILABLE), next two elements are price (low, high)
        """
        num_responses = res[0]
        if num_responses > len(bases):
            return [
                BaseException(
                    f"Got {num_responses} price responses but only {len(bases)} base assets."
                )
            ]

        entries = []
        current_idx = 1
        current_base_idx = 0
        while current_base_idx < num_responses and current_idx < len(res):
            base = bases[current_base_idx]
            pair = Pair.from_tickers(base.id, quote.id)
            status = EkuboStatus(res[current_idx])

            if status == EkuboStatus.PRICE_AVAILABLE:
                if current_idx + 2 >= len(res):
                    return [
                        BaseException(
                            "Incomplete price data in the Price Fetcher response."
                        )
                    ]

                entry, idx_increment = self._handle_price_status(current_idx, res, pair)
                entries.append(entry)
            else:
                error, idx_increment = self._handle_error_status(status, pair)
                entries.append(error)

            current_idx += idx_increment
            current_base_idx += 1

        return entries

    def _handle_price_status(
        self,
        current_idx: int,
        res: List[int],
        pair: Pair,
    ) -> Tuple[SpotEntry, int]:
        """
        Handle price available status (3)
        """
        if pair == Pair.from_tickers("EKUBO", "USDC"):
            print(res[current_idx + 1], res[current_idx + 2])
        raw_price = u256_parts_to_int(
            low=res[current_idx + 1], high=res[current_idx + 2]
        )
        decimals = (pair.base_currency.decimals + pair.quote_currency.decimals) / 2
        price_in_usd = (raw_price / (2**128)) * (10**decimals)

        entry = SpotEntry(
            pair_id=pair.id,
            price=price_in_usd,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return entry, 3

    def _handle_error_status(
        self,
        status: EkuboStatus,
        pair: Pair,
    ) -> Tuple[PublisherFetchError, int]:
        """
        Handle error statuses (0, 1, 2)
        """
        error_messages = {
            EkuboStatus.NOT_INITIALIZED: f"Price feed not initialized for {pair} in Ekubo",
            EkuboStatus.INSUFFICIENT_LIQUIDITY: f"Insufficient liquidity for {pair} in Ekubo",
            EkuboStatus.PERIOD_TOO_LONG: f"Period too long for {pair}",
        }
        return PublisherFetchError(error_messages[status]), 1

    def _compute_price_in_usd(
        self, raw_price: int, base: Currency, quote: Currency
    ) -> int:
        """
        Converts a Raw price returned from the Ekubo Price Fetcher contract into a
        price in $.
        """
        decimals = (base.decimals + quote.decimals) / 2
        return (raw_price / (2**128)) * (10**decimals)

    def _group_pairs_by_quote(
        self, pairs: List[Pair]
    ) -> Dict[Currency, List[Currency]]:
        """
        Groups a list of Pair by their quote currency.

        Example, with this set of pairs:
            - Pair(BTC, USD)
            - Pair(ETH, USD)
            - Pair(DOGE, ETH)

        We will get:
        {
            USD: [BTC, ETH],
            ETH: [DOGE]
        }
        all elements being of type `Currency`.
        """
        grouped_pairs = {}
        for pair in pairs:
            quote_currency = pair.quote_currency
            if quote_currency not in grouped_pairs:
                grouped_pairs[quote_currency] = []
            grouped_pairs[quote_currency].append(pair.base_currency)
        return grouped_pairs

    async def fetch_pair(
        self, pair: Pair, session: ClientSession
    ) -> Entry | PublisherFetchError:
        raise NotImplementedError("`fetch_pair` is not needed for the Ekubo Fetcher.")

    def format_url(self, pair: Pair) -> str:
        raise NotImplementedError("`format_url` is not needed for the Ekubo Fetcher.")


import aiohttp
import asyncio


async def main():
    ekubo = EkuboFetcher(
        pairs=[
            Pair.from_tickers("EKUBO", "USD"),
        ],
        publisher="ADEL",
        network="mainnet",
    )

    async with aiohttp.ClientSession() as session:
        entries = await ekubo.fetch(session)
        print(entries)
        print("✅ Ok!")


if __name__ == "__main__":
    asyncio.run(main())
