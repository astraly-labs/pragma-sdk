import asyncio

from dataclasses import field

from typing import Dict, Optional
from aiohttp import ClientSession
from pydantic.dataclasses import dataclass

from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.configs.asset_config import AssetConfig
from pragma_sdk.common.fetchers.handlers.reference_price import (
    ReferencePriceProvider,
    get_reference_price_provider,
)


@dataclass
class HopHandler:
    """
    Dataclass in charge of handling pair hopping.
    Is mostly integrated within fetchers to handle different quote currencies.

    :param hopped_currencies: Dict between the quote currency and the new quote currency
    """

    hopped_currencies: Dict[str, str] = field(default_factory=dict)

    def get_hop_pair(self, pair: Pair) -> Optional[Pair]:
        """
        Returns a new pair if the quote currency is in the hopped_currencies list
        Otherwise, returns None

        :param pair: Pair
        :return: Optional[Pair]
        """

        if pair.quote_currency.id not in self.hopped_currencies:
            return None

        new_currency_id = self.hopped_currencies[pair.quote_currency.id]

        # Skip degenerate hops where the base already equals the hop target
        # (e.g. USDT/USD with a USD->USDT hop would become USDT/USDT, which no
        # exchange lists). Returning None lets the fetcher query the pair directly.
        if new_currency_id == pair.base_currency.id:
            return None

        return Pair(
            pair.base_currency,
            Currency.from_asset_config(AssetConfig.from_ticker(new_currency_id)),
        )

    async def get_hop_prices(
        self,
        session: Optional[ClientSession] = None,
        provider: Optional[ReferencePriceProvider] = None,
    ) -> Dict[Pair, float]:
        """
        For each hopped currency, the price between the two currencies, taken
        from independent off-chain references and never from Pragma's own
        oracle (that would be a feedback loop, see reference_price.py).

        For example, with hopped currencies {"USD": "USDC"} and {"USD": "ETH"}
        we return {Pair("USDC/USD"): 1.0, Pair("ETH/USD"): <cex median>}.

        Raises ReferencePriceError when a reference cannot be established: the
        caller must fail closed for its hopped pairs.
        """
        provider = provider or get_reference_price_provider()

        async def fetch_single_price(
            from_currency: str, to_currency: str
        ) -> tuple[Pair, float]:
            pair = Pair.from_tickers(to_currency, from_currency)
            price = await provider.get_price(to_currency, from_currency, session)
            return pair, price

        tasks = [
            fetch_single_price(from_currency, to_currency)
            for from_currency, to_currency in self.hopped_currencies.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        prices: Dict[Pair, float] = {}
        for result in results:
            if isinstance(result, BaseException):
                raise result
            pair, price = result
            prices[pair] = price

        return prices
