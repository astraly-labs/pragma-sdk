import time

from typing import Optional, List, Dict, Any, Tuple

from pydantic.dataclasses import dataclass
from starknet_py.utils.merkle_tree import MerkleTree
from starknet_py.hash.utils import compute_hash_on_elements
from starknet_py.cairo.felt import encode_shortstring

from pragma_sdk.common.types.types import UnixTimestamp, Decimals


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
    current_timestamp: UnixTimestamp
    mark_price: int

    @classmethod
    def from_deribit_response(
        cls,
        response: DeribitOptionResponse,
        decimals: Decimals,
    ) -> "OptionData":
        current_timestamp = int(time.time())
        mark_price = (response.mark_price * response.underlying_price) * (10**decimals)
        return cls(
            instrument_name=response.instrument_name,
            base_currency=response.base_currency,
            current_timestamp=current_timestamp,
            mark_price=int(mark_price),
        )

    def as_dict(self) -> dict:
        return {
            "instrument_name": self.instrument_name,
            "base_currency": self.base_currency,
            "current_timestamp": self.current_timestamp,
            "mark_price": self.mark_price,
        }

    def get_pedersen_hash(self) -> int:
        """
        Computes the Pedersen hash of the OptionData.

        NOTE: We don't implement the `__hash__` method, because under the hood
        it will truncate your hash so it is maximum 64 bytes. Which won't work
        with our implementation because we need more space. 😹
        """
        to_hash = [
            encode_shortstring(self.instrument_name),
            encode_shortstring(self.base_currency),
            self.current_timestamp,
            self.mark_price,
        ]
        return compute_hash_on_elements(to_hash)  # type: ignore[no-any-return]

    def serialize(self) -> Dict[str, int]:
        return {
            "instrument_name": encode_shortstring(self.instrument_name),
            "base_currency_id": encode_shortstring(self.base_currency),
            "current_timestamp": self.current_timestamp,
            "mark_price": self.mark_price,
        }


CurrenciesOptions = Dict[str, List[OptionData]]


@dataclass
class LatestData:
    merkle_tree: MerkleTree
    options: CurrenciesOptions
