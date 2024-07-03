import re

from enum import StrEnum, unique
from collections import namedtuple
from typing import Optional, Literal, Union, List
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


@dataclass
class VRFSubmitParams:
    request_id: int
    requestor_address: int
    seed: int
    callback_address: int
    callback_fee_limit: int
    minimum_block_number: int
    random_words: List[int]
    proof: List[int]
    calldata: List[int]
    callback_fee: Optional[int] = None


@dataclass
class VRFCancelParams:
    request_id: int
    requestor_address: int
    seed: int
    callback_address: int
    callback_fee_limit: int
    minimum_block_number: int
    num_words: int
