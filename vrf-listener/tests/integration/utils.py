import logging
from typing import Optional, List
from pathlib import Path

from starknet_py.net.client import Client

from pragma_sdk.onchain.abis.abi import ABIS
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types import Contract, ContractAddresses

from tests.integration.constants import CONTRACTS_COMPILED_DIR

logger = logging.getLogger(__name__)


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

    async def example_get_last_random(self):
        (response,) = await self.example_randomness.functions["get_last_random"].call()
        return response


class ExtendedPragmaClient(PragmaOnChainClient, ExampleRandomnessMixin):
    def __init__(
        self,
        network: str = "devnet",
        account_private_key: Optional[int] = None,
        account_contract_address: Optional[int] = None,
        contract_addresses_config: Optional[ContractAddresses] = None,
        port: Optional[int] = None,
        chain_name: Optional[str] = None,
    ):
        super().__init__(
            network=network,
            account_private_key=account_private_key,
            account_contract_address=account_contract_address,
            contract_addresses_config=contract_addresses_config,
            port=port,
            chain_name=chain_name,
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


def are_entries_list_equal[T](a: List[T], b: List[T]) -> bool:
    """
    Check if two lists of entries are equal no matter the order.

    :param a: List of entries
    :param b: List of entries
    :return: True if equal, False otherwise
    """

    return set(a) == set(b)
