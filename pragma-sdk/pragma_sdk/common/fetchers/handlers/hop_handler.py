import asyncio

from dataclasses import field

from typing import Dict, Optional
from pydantic.dataclasses import dataclass

from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.configs.asset_config import AssetConfig

from pragma_sdk.onchain.client import PragmaOnChainClient


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

        return Pair(
            pair.base_currency,
            Currency.from_asset_config(AssetConfig.from_ticker(new_currency_id)),
        )

    async def get_hop_prices(self, client: PragmaOnChainClient) -> Dict[Pair, float]:
        """
        For each hopped currencies, compute the price between the two currencies.

        For example, if our hopped currencies are:
        {
            "USD": "USDC",
            "ETH": "STETH",
        }

        We will return:
        {
            Pair("USDC/USD"): price,
            Pair("STETH/ETH"): price,
        }
        """

        # Sub-task that will be ran asynchronously, fetching a price for a given
        # couple (from, to) currencies.
        async def fetch_single_price(
            from_currency: str, to_currency: str
        ) -> tuple[Pair, float]:
            pair = Pair.from_tickers(to_currency, from_currency)
            response = await client.get_spot(pair.id)
            price = int(response.price) / int(10 ** int(response.decimals))
            return pair, price

        tasks = [
            fetch_single_price(from_currency, to_currency)
            for from_currency, to_currency in self.hopped_currencies.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        prices: Dict[Pair, float] = {}
        for result in results:
            if isinstance(result, Exception):
                raise result
            pair, price = result  # type: ignore[misc]
            prices[pair] = price

        return prices
