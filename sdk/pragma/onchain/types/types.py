from enum import StrEnum, unique
from collections import namedtuple
from typing import Optional, Literal, Union, List, Any
from pydantic import HttpUrl

from pydantic.dataclasses import dataclass

from pragma.common.types.types import ADDRESS

ContractAddresses = namedtuple(
    "ContractAddresses", ["publisher_registry_address", "oracle_proxy_addresss"]
)

Network = Union[
    Literal[
        "devnet",
        "mainnet",
        "sepolia",
    ],
    HttpUrl,
]


@unique
class RequestStatus(StrEnum):
    UNINITIALIZED = "UNINITIALIZED"
    RECEIVED = "RECEIVED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    OUT_OF_GAS = "OUT_OF_GAS"
    REFUNDED = "REFUNDED"

    def serialize(self):
        return {self.value: None}


OracleResponse = namedtuple(
    "OracleResponse",
    [
        "price",
        "decimals",
        "last_updated_timestamp",
        "num_sources_aggregated",
        "expiration_timestamp",
    ],
)


@dataclass
class VRFRequestParams:
    seed: int
    callback_address: ADDRESS
    callback_fee_limit: int = 1000000
    publish_delay: int = 1
    num_words: int = 1
    calldata: Optional[List[int]] = None

    def __post_init__(self):
        if self.calldata is None:
            self.calldata = []

    def to_list(self) -> List[Any]:
        result = [
            self.seed,
            self.callback_address,
            self.callback_fee_limit,
            self.publish_delay,
            self.num_words,
            self.calldata,
        ]
        return result


@dataclass
class VRFSubmitParams:
    request_id: int
    requestor_address: int
    seed: int
    minimum_block_number: int
    callback_address: int
    callback_fee_limit: int
    random_words: List[int]
    proof: List[int]
    calldata: Optional[List[int]] = None
    callback_fee: Optional[int] = None

    def __post_init__(self):
        if self.calldata is None:
            self.calldata = []
        if self.callback_fee is None:
            self.callback_fee = 0

    def to_list(self) -> List[Any]:
        result = [
            self.request_id,
            self.requestor_address,
            self.seed,
            self.minimum_block_number,
            self.callback_address,
            self.callback_fee_limit,
            self.callback_fee,
            self.random_words,
            self.proof,
            self.calldata,
        ]
        return result


@dataclass
class VRFCancelParams:
    request_id: int
    requestor_address: int
    seed: int
    minimum_block_number: int
    callback_address: int
    callback_fee_limit: int
    num_words: int

    def to_list(self) -> List[Any]:
        return [
            self.request_id,
            self.requestor_address,
            self.seed,
            self.minimum_block_number,
            self.callback_address,
            self.callback_fee_limit,
            self.num_words,
        ]
