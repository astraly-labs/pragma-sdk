from pydantic.dataclasses import dataclass
import secrets
import sys
from typing import List

from pragma_sdk.common.types.types import ADDRESS

from pragma_sdk.common.randomness.randomness_utils import (
    ecvrf_proof_to_hash,
    ecvrf_prove,
    ecvrf_verify,
    get_public_key,
)


@dataclass(frozen=True)
class RandomnessRequest:
    request_id: int
    caller_address: ADDRESS
    seed: int
    minimum_block_number: int
    callback_address: ADDRESS
    callback_fee_limit: int
    num_words: int
    calldata: List[int]

    def __repr__(self):
        return (
            f"Request(caller_address={self.caller_address},request_id={self.request_id},"
            f"minimum_block_number={self.minimum_block_number}"
        )


def make_secret_key():
    return secrets.token_bytes(nbytes=32)


def felt_to_secret_key(felt: int):
    return felt.to_bytes(32, sys.byteorder)


def uint256_to_2_128(num: int):
    num_as_bytes = num.to_bytes(32, sys.byteorder)
    return (
        int.from_bytes(num_as_bytes[:16], sys.byteorder),
        int.from_bytes(num_as_bytes[16:], sys.byteorder),
    )


def create_randomness(
    secret_key,
    seed: int,
):
    # Alice generates a secret and public key pair
    public_key = get_public_key(secret_key)

    _, pi_string = ecvrf_prove(secret_key, seed)
    b_status, beta_string = ecvrf_proof_to_hash(pi_string)
    assert b_status == "VALID"

    return beta_string, pi_string, public_key


def verify_randomness(
    public_key,
    proof_,
    seed: int,
):
    seed_as_bytes = seed.to_bytes(32, sys.byteorder)[:32]
    result, _ = ecvrf_verify(public_key, proof_, seed_as_bytes)
    return result
