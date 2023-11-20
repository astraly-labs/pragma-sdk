import secrets
import sys
from typing import List

import requests
from starknet_py.net.networks import TESTNET

from .randomness_utils import (
    ecvrf_proof_to_hash,
    ecvrf_prove,
    ecvrf_verify,
    get_public_key,
)


class RandomnessRequest:
    def __init__(
        self,
        request_id,
        caller_address,
        seed,
        minimum_block_number,
        callback_address,
        callback_gas_limit,
        num_words,
    ):
        self.request_id = int(request_id, 16)
        self.caller_address = int(caller_address, 16)
        self.seed = int(seed, 16)
        self.minimum_block_number = int(minimum_block_number, 16)
        self.callback_address = int(callback_address, 16)
        self.callback_gas_limit = int(callback_gas_limit, 16)
        self.num_words = int(num_words, 16)

    def __repr__(self):
        return (
            f"Request(caller_address={self.caller_address},request_id={self.request_id},"
            f"minimum_block_number={self.minimum_block_number}"
        )


def make_secret_key():
    return secrets.token_bytes(nbytes=32)


def felt_to_secret_key(sk):
    return sk.to_bytes(32, sys.byteorder)


def uint256_to_2_128(num: int):
    num = num.to_bytes(32, sys.byteorder)
    return (
        int.from_bytes(num[:16], sys.byteorder),
        int.from_bytes(num[16:], sys.byteorder),
    )


def create_randomness(
    secret_key,
    seed: int,
):
    # Alice generates a secret and public key pair
    public_key = get_public_key(secret_key)

    p_status, pi_string = ecvrf_prove(secret_key, seed)
    b_status, beta_string = ecvrf_proof_to_hash(pi_string)
    assert b_status == "VALID"

    return beta_string, pi_string, public_key


def verify_randomness(
    public_key,
    proof_,
    seed: int,
):
    seed = seed.to_bytes(32, sys.byteorder)[:32]
    result, beta_string2 = ecvrf_verify(public_key, proof_, seed)
    return result
