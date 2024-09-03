from typing import Optional, Literal

from pydantic import HttpUrl

from starknet_py.net.client import Client
from starknet_py.contract import Contract

from pragma_sdk.onchain.abis.abi import get_erc20_abi, ABIS
from pragma_sdk.onchain.types import (
    ContractAddresses,
)
from pragma_sdk.onchain.client import PragmaOnChainClient

from benchmark.constants import FEE_TOKEN_ADDRESS


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


async def create_pragma_client(
    network: Literal["devnet", "mainnet", "sepolia"],
    rpc_url: HttpUrl,
    randomness_contracts: (Contract, Contract, Contract),
    account_address: str,
    private_key: str,
) -> ExtendedPragmaClient:
    (randomness, example, oracle) = randomness_contracts

    client = ExtendedPragmaClient(
        chain_name=network,
        network=rpc_url,
        account_contract_address=account_address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=oracle.address,
            summary_stats_address=0x0,
        ),
    )
    client.init_randomness_contract(randomness.address)
    client.init_example_randomness_contract(example.address)

    # Approve randomness contract to transfer fee tokens
    erc20_contract = Contract(
        address=FEE_TOKEN_ADDRESS,
        abi=get_erc20_abi(),
        provider=client.account,
        cairo_version=0,
    )
    invocation = await erc20_contract.functions["approve"].invoke_v1(
        randomness.address, 0xFFFFFFFFFFFFFFFFFFFFFFFF, auto_estimate=True
    )
    await invocation.wait_for_acceptance()

    return client
