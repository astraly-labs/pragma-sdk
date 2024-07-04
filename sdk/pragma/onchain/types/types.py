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

    def to_list(self) -> List[Any]:
        result = [
            self.seed,
            self.callback_address,
            self.callback_fee_limit,
            self.publish_delay,
            self.num_words,
        ]
        result.append(self.calldata if self.calldata is not None else [])
        return result


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

    def to_list(self) -> List[Any]:
        result = [
            self.request_id,
            self.requestor_address,
            self.seed,
            self.callback_address,
            self.callback_fee_limit,
            self.minimum_block_number,
            self.random_words,
            self.proof,
            self.calldata,
        ]
        if self.callback_fee:
            result.append(self.callback_fee)
        else:
            result.append(1000000)
        return result


@dataclass
class VRFCancelParams:
    request_id: int
    requestor_address: int
    seed: int
    callback_address: int
    callback_fee_limit: int
    minimum_block_number: int
    num_words: int

    def to_list(self) -> List[Any]:
        return [
            self.request_id,
            self.requestor_address,
            self.seed,
            self.callback_address,
            self.callback_fee_limit,
            self.minimum_block_number,
            self.num_words,
        ]
