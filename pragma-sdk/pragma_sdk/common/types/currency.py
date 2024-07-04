from typing import List, Optional, Self

from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.common.types.types import ADDRESS, DECIMALS
from pragma_sdk.common.configs.asset_config import AssetConfig


class Currency:
    id: str
    decimals: DECIMALS
    is_abstract_currency: bool
    starknet_address: ADDRESS
    ethereum_address: ADDRESS

    def __init__(
        self,
        currency_id: str,
        decimals: DECIMALS,
        is_abstract_currency: bool,
        starknet_address: Optional[ADDRESS] = None,
        ethereum_address: Optional[ADDRESS] = None,
    ):
        self.id = currency_id

        self.decimals = decimals

        if isinstance(is_abstract_currency, int):
            is_abstract_currency = bool(is_abstract_currency)
        self.is_abstract_currency = is_abstract_currency

        if starknet_address is None:
            starknet_address = 0
        self.starknet_address = starknet_address

        if ethereum_address is None:
            ethereum_address = 0
        self.ethereum_address = ethereum_address

    @classmethod
    def from_asset_config(cls, config: AssetConfig) -> Self:
        return cls(
            currency_id=config.ticker,
            decimals=config.decimals,
            is_abstract_currency=config.abstract,
        )

    def serialize(self) -> List[str]:
        return [
            self.id,
            self.decimals,
            self.is_abstract_currency,
            self.starknet_address,
            self.ethereum_address,
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "decimals": self.decimals,
            "is_abstract_currency": self.is_abstract_currency,
            "starknet_address": self.starknet_address,
            "ethereum_address": self.ethereum_address,
        }

    def __repr__(self):
        return (
            f"Currency({str_to_felt(self.id)}, {self.decimals}, "
            f"{self.is_abstract_currency}, {self.starknet_address},"
            f" {self.ethereum_address})"
        )

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Currency):
            return False
        return (
            self.id == value.id
            and self.decimals == value.decimals
            and self.is_abstract_currency == value.is_abstract_currency
            and self.starknet_address == value.starknet_address
            and self.ethereum_address == value.ethereum_address
        )
