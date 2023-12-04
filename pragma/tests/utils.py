import random
from pathlib import Path
from typing import Optional, cast

import json
import os 
from starknet_py.constants import EC_ORDER
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.net.models import StarknetChainId
from starknet_py.net.models.transaction import DeployAccount
from starknet_py.net.networks import Network
from starknet_py.net.signer.stark_curve_signer import KeyPair

from pragma.tests.constants import CONTRACTS_COMPILED_DIR, MAX_FEE
from pragma.tests.constants import DEPLOYMENTS_DIR

def read_contract(file_name: str, *, directory: Optional[Path] = None) -> str:
    """
    Return contents of file_name from directory.
    """
    if directory is None:
        directory = CONTRACTS_COMPILED_DIR

    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist!")

    return (directory / file_name).read_text("utf-8")


def _get_random_private_key_unsafe() -> int:
    """
    Returns a private key in the range [1, EC_ORDER).
    This is not a safe way of generating private keys and should be used only in tests.
    """
    return random.randint(1, EC_ORDER - 1)


async def get_deploy_account_transaction(
    *, address: int, key_pair: KeyPair, salt: int, class_hash: int, client: Client
) -> DeployAccount:
    """
    Get a signed DeployAccount transaction from provided details
    """

    account = Account(
        address=address,
        client=client,
        key_pair=key_pair,
        chain=StarknetChainId.TESTNET,
    )
    return await account.sign_deploy_account_transaction(
        class_hash=class_hash,
        contract_address_salt=salt,
        constructor_calldata=[key_pair.public_key],
        max_fee=int(1e16),
    )

def get_declarations():
    return {
        name: int(class_hash, 16)
        for name, class_hash in json.load(
            open(DEPLOYMENTS_DIR / "declarations.json")
        ).items()
    }


def get_deployments():
    return json.load(open(DEPLOYMENTS_DIR / "pragma-oracle/deployments/testnet/deployments.json", "r"))
