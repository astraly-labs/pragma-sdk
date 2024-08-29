import secrets
import sys

from typing import Tuple

from pragma_sdk.common.randomness.randomness_utils import (
    ecvrf_proof_to_hash,
    ecvrf_prove,
    ecvrf_verify,
    get_public_key,
)


def make_secret_key() -> bytes:
    return secrets.token_bytes(nbytes=32)


def felt_to_secret_key(felt: int) -> bytes:
    return felt.to_bytes(32, sys.byteorder)


def uint256_to_2_128(num: int) -> Tuple[int, int]:
    num_as_bytes = num.to_bytes(32, sys.byteorder)
    return (
        int.from_bytes(num_as_bytes[:16], sys.byteorder),
        int.from_bytes(num_as_bytes[16:], sys.byteorder),
    )


def create_randomness(
    secret_key: bytes,
    seed: bytes,
) -> Tuple[str, str, str]:
    # Alice generates a secret and public key pair
    public_key = get_public_key(secret_key)

    _, pi_string = ecvrf_prove(secret_key, seed)  # type: ignore[no-untyped-call]
    b_status, beta_string = ecvrf_proof_to_hash(pi_string)  # type: ignore[no-untyped-call]
    assert b_status == "VALID"

    return beta_string, pi_string, public_key


def verify_randomness(
    public_key: str,
    proof_: str,
    seed: int,
) -> str:
    seed_as_bytes = seed.to_bytes(32, sys.byteorder)[:32]
    result, _ = ecvrf_verify(public_key, proof_, seed_as_bytes)  # type: ignore[no-untyped-call, unused-ignore]
    return result  # type: ignore[no-any-return]
