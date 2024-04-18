import json
import os
import random
from pathlib import Path
from typing import Optional

from starknet_py.net.account.account import Account
from starknet_py.net.client import Client
from starknet_py.net.models import StarknetChainId
from starknet_py.net.models.transaction import DeployAccount
from starknet_py.net.networks import Network
from starknet_py.net.signer.stark_curve_signer import KeyPair

from pragma.core.abis import ABIS
from pragma.core.client import PragmaClient
from pragma.core.contract import Contract
from pragma.core.types import PRAGMA_API_URL, ContractAddresses
from pragma.tests.constants import (
    CONTRACTS_COMPILED_DIR,
    DEPLOYMENTS_DIR,
    MAX_FEE,
    ORACLE_DECIMALS,
    ORACLE_FEE_PRICE,
)


def read_contract(file_name: str, *, directory: Optional[Path] = None) -> str:
    """
    Return contents of file_name from directory.
    """
    if directory is None:
        directory = CONTRACTS_COMPILED_DIR

    if not directory.exists():
        raise ValueError(f"Directory {directory} does not exist!")

    return (directory / file_name).read_text("utf-8")


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
        chain=StarknetChainId.SEPOLIA_TESTNET,
    )
    return await account.sign_deploy_account_v1_transaction(
        class_hash=class_hash,
        contract_address_salt=salt,
        constructor_calldata=[key_pair.public_key],
        max_fee=int(1e16),
    )


def get_declarations(network: Network):
    return {
        name: int(class_hash, 16)
        for name, class_hash in json.load(
            open(DEPLOYMENTS_DIR / f"{network}" / "declarations.json")
        ).items()
    }


def get_deployments(network: Network):
    return json.load(open(DEPLOYMENTS_DIR / f"{network}" / "deployments.json", "r"))


def convert_to_wei(usd):
    res = (usd * 1000000000000000000 * 10**ORACLE_DECIMALS) / (
        ORACLE_FEE_PRICE * 100000000
    )
    return res


class ExampleRandomnessMixin:
    client: Client
    example_randomness: Optional[Contract] = None

    def init_example_randomness_contract(self, example_contract_address: int):
        provider = self.account if self.account else self.client

        self.example_randomness = Contract(
            address=example_contract_address,
            abi=ABIS["pragma_ExampleRandomness"],
            provider=provider,
            cairo_version=1,
        )

    async def get_last_example_random(self):
        (response,) = await self.example_randomness.functions["get_last_random"].call()
        return response

    async def example_request_random(
        self,
        seed: int,
        callback_address: int,
        callback_fee_limit: int,
        publish_delay: int,
        num_words: int,
    ):
        if not self.is_user_client:
            raise AttributeError(
                "Must set account. You may do this by invoking self._setup_account_client(private_key, account_contract_address)"
            )
        invocation = await self.example_randomness.functions[
            "request_random"
        ].invoke_v1(
            seed, callback_address, callback_fee_limit, publish_delay, num_words
        )
        return invocation


class ExtendedPragmaClient(PragmaClient, ExampleRandomnessMixin):
    def __init__(
        self,
        network: str = "devnet",
        account_private_key: Optional[int] = None,
        account_contract_address: Optional[int] = None,
        contract_addresses_config: Optional[ContractAddresses] = None,
        port: Optional[int] = None,
        chain_name: Optional[str] = None,
        api_url: Optional[str] = PRAGMA_API_URL,
        api_key: Optional[str] = None,
    ):
        super().__init__(
            network=network,
            account_private_key=account_private_key,
            account_contract_address=account_contract_address,
            contract_addresses_config=contract_addresses_config,
            port=port,
            chain_name=chain_name,
            api_url=api_url,
            api_key=api_key,
        )
        # Any additional initialization for ExampleRandomnessMixin can be done here

    # You can override or add new methods here if needed


def filter_assets_by_type(assets, type_):
    """
    Filter the given assets list by the given type.

    e.g
    filter_assets_by_type(SAMPLE_ASSETS, "SPOT")
    """
    return [assets[i] for i in range(len(assets)) if assets[i]["type"] == type_]


async def wait_for_acceptance(invocation):
    await invocation.wait_for_acceptance()
