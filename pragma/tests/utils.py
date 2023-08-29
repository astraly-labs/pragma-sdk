import random
from pathlib import Path
from typing import Optional, cast

from starknet_py.constants import EC_ORDER
from starknet_py.contract import Contract
from starknet_py.hash.address import compute_address
from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.net.gateway_client import GatewayClient
from starknet_py.net.http_client import HttpClient, HttpMethod
from starknet_py.net.models import StarknetChainId
from starknet_py.net.models.transaction import DeployAccount
from starknet_py.net.networks import Network
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.udc_deployer.deployer import _get_random_salt

from pragma.core.abis.abi import CONTRACTS_COMPILED_DIR
from pragma.tests.constants import MAX_FEE


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
    *,
    address: int,
    key_pair: KeyPair,
    salt: int,
    class_hash: int,
    network: Optional[Network] = None,
    client: Optional[Client] = None,
) -> DeployAccount:
    """
    Get a signed DeployAccount transaction from provided details
    """
    if network is None and client is None:
        raise ValueError("One of network or client must be provided.")

    account = Account(
        address=address,
        client=client
        or GatewayClient(
            net=cast(
                Network, network
            )  # Cast needed because pyright doesn't recognize network as not None at this point
        ),
        key_pair=key_pair,
        chain=StarknetChainId.TESTNET,
    )
    return await account.sign_deploy_account_transaction(
        class_hash=class_hash,
        contract_address_salt=salt,
        constructor_calldata=[key_pair.public_key],
        max_fee=MAX_FEE,
    )
