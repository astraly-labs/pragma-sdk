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
from pragma_sdk.common.utils import uint256_to_int

from pragma_sdk.onchain.types.types import Network

logger = get_pragma_sdk_logger()

PRICE_FETCHER_CONTRACT = {
    "sepolia": "0x04613bee55d8a37adfa249b24c6b13451dedf7cf4f02d01de859579119de3add",
    "mainnet": "0x04946fb4ad5237d97bbb1256eba2080c4fe1de156da6a7f83e3b4823bb6d7da1",
}

GET_PRICES_SELECTOR = get_selector_from_name("get_prices")
PERIOD = 3600  # one hour
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
        self,
        session: ClientSession,
    ) -> List[Entry | PublisherFetchError | BaseException]:
        """
        Fetches the data from the fetcher and returns a list of Entry objects.
        """
        pairs = [self.hop_handler.get_hop_pair(pair) or pair for pair in self.pairs]
        groupped_pairs = self._group_pairs_by_quote(pairs)
        entries = []
        for quote_currency, base_currencies in groupped_pairs.items():
            response = await self._call_get_prices(quote_currency, base_currencies)
            new_entries = await self._parse_response_into_entries(
                quote_currency, base_currencies, response
            )
            entries.extend(new_entries)
        return entries  # type: ignore[call-overload]

    async def _call_get_prices(
        self,
        quote: Currency,
        bases: List[Currency],
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

    async def _parse_response_into_entries(
        self,
        quote: Currency,
        bases: List[Currency],
        res: List[int],
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

                entry, idx_increment = await self._handle_price_status(
                    current_idx, res, pair
                )
                entries.append(entry)
            else:
                error, idx_increment = self._handle_error_status(status, pair)
                entries.append(error)

            current_idx += idx_increment
            current_base_idx += 1

        return entries

    async def _handle_price_status(
        self,
        current_idx: int,
        res: List[int],
        pair: Pair,
    ) -> Tuple[SpotEntry, int]:
        """
        Handle price available status (3)
        """
        raw_price = uint256_to_int(low=res[current_idx + 1], high=res[current_idx + 2])
        price = self._compute_price_in_usd(raw_price, pair)

        if pair.quote_currency.id in self.hop_handler.hopped_currencies.values():
            price, pair = await self._adapt_back_hopped_pair(price, pair)
        else:
            price = price * 10**pair.quote_currency.decimals

        price_int = int(price)
        logger.debug("Fetched price %d for %s from Ekubo", price_int, pair)

        entry = SpotEntry(
            pair_id=pair.id,
            price=price_int,
            timestamp=int(time.time()),
            source=self.SOURCE,
            publisher=self.publisher,
        )
        return entry, 3

    async def _adapt_back_hopped_pair(
        self, price: int, pair: Pair
    ) -> Tuple[float, Pair]:
        hop = (None, None)
        for asset, hopped_to in self.hop_handler.hopped_currencies.items():
            if hopped_to == pair.quote_currency.id:
                hop = (asset, hopped_to)
                break
        if hop == (None, None):
            raise ValueError("Should never happen since we hopped in the first place.")

        hop_price = await self.get_stable_price(hop[1])
        new_pair = Pair.from_tickers(pair.base_currency.id, hop[0])

        return (
            price * hop_price * 10**new_pair.quote_currency.decimals,
            new_pair,
        )

    def _handle_error_status(
        self, status: EkuboStatus, pair: Pair, è
    ) -> Tuple[PublisherFetchError, int]:
        """
        Handle error statuses (0, 1, 2) & returns the associated PublisherFetchError
        """
        error_messages = {
            EkuboStatus.NOT_INITIALIZED: f"Price feed not initialized for {pair} in Ekubo",
            EkuboStatus.INSUFFICIENT_LIQUIDITY: f"Insufficient liquidity for {pair} in Ekubo",
            EkuboStatus.PERIOD_TOO_LONG: f"Period too long for {pair}",
        }
        return PublisherFetchError(error_messages[status]), 1

    def _compute_price_in_usd(self, raw_price: int, pair: Pair) -> float:
        """
        Converts a Raw price returned from the Ekubo Price Fetcher contract into a price in $.
        """
        decimals = abs(pair.quote_currency.decimals - pair.base_currency.decimals)
        return (raw_price / (2**128)) * (10**decimals)

    def _group_pairs_by_quote(
        self,
        pairs: List[Pair],
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
        self,
        pair: Pair,
        session: ClientSession,
    ) -> Entry | PublisherFetchError:
        raise NotImplementedError("`fetch_pair` is not needed for the Ekubo Fetcher.")

    def format_url(self, pair: Pair) -> str:
        raise NotImplementedError("`format_url` is not needed for the Ekubo Fetcher.")


import aiohttp
import asyncio

from pragma_sdk.common.fetchers.fetchers.dexscreener import DexscreenerFetcher


async def main():
    pairs = [
        Pair.from_tickers("WBTC", "USD"),
        Pair.from_tickers("EKUBO", "USD"),
        Pair.from_tickers("LORDS", "USD"),
        Pair.from_tickers("ETH", "USD"),
        Pair.from_tickers("ZEND", "USD"),
        Pair.from_tickers("EKUBO", "ETH"),
    ]
    ekubo = EkuboFetcher(
        pairs=pairs,
        publisher="ADEL",
        network="mainnet",
    )

    dex = DexscreenerFetcher(pairs=pairs, publisher="ADEL", network="mainnet")

    async with aiohttp.ClientSession() as session:
        entries = await ekubo.fetch(session)
        print(entries)
        print("✅ Ok!")

    async with aiohttp.ClientSession() as session:
        entries = await dex.fetch(session)
        print(entries)
        print("✅ Ok!")


if __name__ == "__main__":
    asyncio.run(main())
