import collections
from pydantic.dataclasses import dataclass
from typing import List, Optional

from pragma.core.types import ADDRESS

OracleResponse = collections.namedtuple(
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
    callback_fee: Optional[int] = None
    minimum_block_number: int
    random_words: List[int]
    proof: List[int]
    calldata: List[int]


@dataclass
class VRFCancelParams:
    request_id: int
    requestor_address: int
    seed: int
    callback_address: int
    callback_fee_limit: int
    minimum_block_number: int
    num_words: int
