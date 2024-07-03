from typing import List, Tuple


from pragma.common.utils import currency_pair_to_pair_id, str_to_felt
from pragma.common.types.currency import Currency


class Pair:
    id: int
    base_currency: Currency
    quote_currency: Currency

    def __init__(self, base_currency: Currency, quote_currency: Currency):
        self.id = str_to_felt(
            currency_pair_to_pair_id(base_currency.id, quote_currency.id)
        )

        if isinstance(base_currency, str):
            base_currency = str_to_felt(base_currency)
        self.base_currency = base_currency

        if isinstance(quote_currency, str):
            quote_currency = str_to_felt(quote_currency)
        self.quote_currency = quote_currency

    def serialize(self) -> List[str]:
        return [self.id, self.base_currency, self.quote_currency]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "base_currency_id": self.base_currency.id,
            "quote_currency_id": self.quote_currency.id,
        }

    def __repr__(self):
        return f"{self.base_currency.id}/{self.quote_currency.id}"

    def to_tuple(self) -> Tuple[str, str]:
        return (self.base_currency.id, self.quote_currency.id)

    def decimals(self):
        """
        Returns the decimals of the pair.
        Corresponds to the minimum of both currencies' decimals.
        """
        return min(self.base_currency.decimals, self.quote_currency.decimals)
