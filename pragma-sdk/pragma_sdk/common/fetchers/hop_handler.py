from typing import Dict, Optional
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.configs.asset_config import AssetConfig
from pydantic.dataclasses import dataclass
from dataclasses import field


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
