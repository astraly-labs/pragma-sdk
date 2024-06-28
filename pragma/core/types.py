from dataclasses import dataclass
import logging
import random
import collections
from enum import Enum, unique
from typing import List, Literal, Optional, Union

from starknet_py.net.client_models import ResourceBounds

from pragma.core.constants import RPC_URLS
from pragma.core.logger import get_stream_logger
from pragma.core.utils import currency_pair_to_pair_id, felt_to_str, str_to_felt

import re

logger = get_stream_logger()
logger.setLevel(logging.INFO)


ADDRESS = int
HEX_STR = str
DECIMALS = int
UnixTimestamp = int

HttpUrl = re.compile(r"^http(s)?://.+")

Network = Union[
    Literal[
        "devnet",
        "mainnet",
        "fork_devnet",
        "sepolia",
    ],
    HttpUrl,
]

Environment = Literal["dev", "prod"]


def get_rpc_url(network: Network = "devnet", port: int = 5050) -> str:
    """
    Returns the RPC URL for the given network.
    Will return a random URL in the list if the network is "sepolia" or "mainnet".

    :param network: Network to get the RPC URL for.
    :param port: Port to use for the RPC URL.
    :return: RPC URL.
    """
    match network:
        case str(url) if url.startswith("http"):
            return url
        case "sepolia" | "mainnet":
            urls = RPC_URLS[network]
            return random.choice(urls)
        case "devnet" | "fork_devnet":
            return f"http://127.0.0.1:{port}/rpc"
        case _:
            raise ValueError(f"Unsupported network: {network}")


ContractAddresses = collections.namedtuple(
    "ContractAddresses", ["publisher_registry_address", "oracle_proxy_addresss"]
)


@unique
class AggregationMode(Enum):
    MEDIAN = "Median"
    AVERAGE = "Mean"
    ERROR = "Error"

    def serialize(self):
        return {self.value: None}


@unique
class RequestStatus(Enum):
    UNINITIALIZED = "UNINITIALIZED"
    RECEIVED = "RECEIVED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    OUT_OF_GAS = "OUT_OF_GAS"

    def serialize(self):
        return {self.value: None}


@dataclass(frozen=True)
class ExecutionConfig:
    pagination: Optional[int] = 40
    max_fee: Optional[int] = int(1e18)
    enable_strk_fees: Optional[bool] = False
    l1_resource_bounds: Optional[ResourceBounds] = None
    auto_estimate: Optional[bool] = False


class Currency:
    id: str
    decimals: DECIMALS
    is_abstract_currency: bool
    starknet_address: ADDRESS
    ethereum_address: ADDRESS

    def __init__(
        self,
        id_: str,
        decimals: DECIMALS,
        is_abstract_currency: bool,
        starknet_address: ADDRESS = None,
        ethereum_address: ADDRESS = None,
    ):
        self.id = id_

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
            f"Currency({felt_to_str(self.id)}, {self.decimals}, "
            f"{self.is_abstract_currency}, {self.starknet_address},"
            f" {self.ethereum_address})"
        )


class Pair:
    id: int
    base_currency: Currency
    quote_currency: Currency

    def __init__(self, base_currency: Currency, quote_currency: Currency):
        self.id = felt_to_str(
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
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
        }

    def __repr__(self):
        return (
            f"Pair({felt_to_str(self.id)}, "
            f"{self.base_currency})"
            f"{self.quote_currency}, "
        )

    def decimals(self):
        """
        Returns the decimals of the pair.
        Corresponds to the minimum of both currencies' decimals.
        """
        return min(self.base_currency.decimals, self.quote_currency.decimals)


DataTypes = Enum("DataTypes", ["Spot", "Future"])


class Asset:
    data_type: DataTypes
    pair_id: int
    expiration_timestamp: Optional[int]

    def __init__(
        self,
        data_type: DataTypes,
        pair_id: Union[str, int],
        expiration_timestamp: Optional[int],
    ):
        if isinstance(pair_id, str):
            pair_id = str_to_felt(pair_id)
        elif not isinstance(pair_id, int):
            raise TypeError(
                "Pair ID must be string (will be converted to felt) or integer"
            )

        self.pair_id = pair_id
        self.data_type = data_type
        self.expiration_timestamp = expiration_timestamp

    def serialize(self) -> dict:
        """
        Serialize method used to interact with Cairo contracts.
        """
        if self.data_type == DataTypes.SPOT:
            return {"SpotEntry": self.pair_id}
        if self.data_type == DataTypes.FUTURE:
            return {"FutureEntry": (self.pair_id, self.expiration_timestamp)}
        return {}

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "expiration_timestamp": self.expiration_timestamp,
            "data_type": self.data_type.name,
        }


class BasePragmaException(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message

    def serialize(self):
        return self.message


class UnsupportedAssetError(BasePragmaException):
    pass


class ClientException(BasePragmaException):
    pass


class PoolKey:
    # token0 is the the token with the smaller adddress (sorted by integer value)
    # token1 is the token with the larger address (sorted by integer value)
    # fee is specified as a 0.128 number, so 1% == 2**128 / 100
    # tick_spacing is the minimum spacing between initialized ticks, i.e. ticks that positions may use
    # extension is the address of a contract that implements additional functionality for the pool
    token_0: int
    token_1: int
    fee: int
    tick_spacing: int
    extension: int

    def __init__(
        self,
        token_0: int,
        token_1: int,
        fee: int,
        tick_spacing: int,
        extension: int = 0,
    ):
        self.token_0 = token_0
        self.token_1 = token_1
        self.fee = fee
        self.tick_spacing = tick_spacing
        self.extension = extension

    def serialize(self) -> List[str]:
        return [
            self.token_0,
            self.token_1,
            self.fee,
            self.tick_spacing,
            self.extension,
        ]

    def to_dict(self) -> dict:
        return {
            "token_0": self.token_0,
            "token_1": self.token_1,
            "fee": self.fee,
            "tick_spacing": self.tick_spacing,
            "extension": self.extension,
        }

    def __repr__(self):
        return f"PoolKey({self.token_0}, {self.token_1}, {self.fee}, {self.tick_spacing}, {self.extension})"
