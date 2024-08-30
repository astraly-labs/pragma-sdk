from typing import Tuple, Optional, Literal, Dict

from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account

from pragma_sdk.onchain.abis import ABIS

from benchmark.constants import FEE_TOKEN_ADDRESS

CLASS_HASHES: Dict[Literal["mainnet", "sepolia"], str] = {
    "devnet": "0x5e269051bec902aa2bd421d348e023c3893c4ff93de6c5f4b8964cd67cc3fc5",
    "mainnet": "0x5e269051bec902aa2bd421d348e023c3893c4ff93de6c5f4b8964cd67cc3fc5",
    "sepolia": "0x040a2430b48587833abc2e912335cffd863c010e2c798d005d9bcace56a156fc",
}


async def deploy_randomness_contracts(
    network: Literal["mainnet", "sepolia"],
    deployer: Account,
    oracle_address: Optional[int] = None,
) -> (Contract, Contract, Contract):
    """
    TODO: Don't redeploy the VRF if the admin already has a deployed account with the same
    hash?
    """
    (
        deploy_result,
        deploy_example_result,
        deploy_oracle_result,
    ) = await _deploy_everything(
        network=network,
        deployer=deployer,
        oracle_address=oracle_address,
    )

    if deploy_oracle_result is None:
        assert oracle_address is not None
        oracle_contract = Contract(
            address=oracle_address,
            abi=ABIS["pragma_Oracle"],
            provider=deployer,
        )

    return (
        deploy_result.deployed_contract,
        deploy_example_result.deployed_contract,
        deploy_oracle_result.deployed_contract if deploy_oracle_result else oracle_contract,
    )


async def _deploy_everything(
    network: Literal["mainnet", "sepolia"],
    deployer: Account,
    oracle_address: Optional[int],
) -> Tuple[DeclareResult, DeployResult, DeployResult, Optional[DeployResult]]:
    deploy_oracle_result = None
    if oracle_address is None:
        # Deploy Mock Oracle
        deploy_oracle_result = await Contract.deploy_contract_v1(
            class_hash=CLASS_HASHES[network],
            account=deployer,
            abi=ABIS["pragma_Oracle"],
            constructor_args=[
                deployer.address,  # admin
                0,  # publisher_registry
                [],
                [],
            ],
            auto_estimate=True,
            cairo_version=1,
        )
        await deploy_oracle_result.wait_for_acceptance()
        oracle_address = deploy_oracle_result.deployed_contract.address

    # Deploy Randomness
    deploy_result = await Contract.deploy_contract_v1(
        class_hash="0x2e167703c1deef69c6c5076133d3491fc75d1d1f486e6a8375712d28ff10fa4",
        account=deployer,
        abi=ABIS["pragma_Randomness"],
        constructor_args=[
            deployer.address,
            deployer.signer.public_key,
            int(FEE_TOKEN_ADDRESS, 16),
            oracle_address,
        ],
        auto_estimate=True,
        cairo_version=1,
    )
    await deploy_result.wait_for_acceptance()

    # Deploy Randomness Example
    deploy_example_result = await Contract.deploy_contract_v1(
        class_hash="0x2f8197e47fa9776db20a22e009fdeee079f0387cbc823fad5bf0d8e285e81a7",
        account=deployer,
        abi=ABIS["pragma_ExampleRandomness"],
        constructor_args=[
            deploy_result.deployed_contract.address,
        ],
        auto_estimate=True,
        cairo_version=1,
    )
    await deploy_example_result.wait_for_acceptance()

    return deploy_result, deploy_example_result, deploy_oracle_result
