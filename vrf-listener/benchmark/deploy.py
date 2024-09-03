from typing import Tuple, Optional, Literal

from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account

from pragma_sdk.onchain.abis import ABIS

from benchmark.constants import FEE_TOKEN_ADDRESS
from benchmark.devnet.contracts import read_contract


async def deploy_randomness_contracts(
    network: Literal["mainnet", "sepolia"],
    deployer: Account,
    oracle_address: Optional[int] = None,
) -> (Contract, Contract, Contract):
    """
    TODO: Don't redeploy if the admin already has a deployed account with same hash?
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
        compiled_oracle_mock_contract = read_contract(
            "pragma_MockOracle.sierra.json", directory=None
        )
        compiled_oracle_mock_contract_casm = read_contract(
            "pragma_MockOracle.casm.json", directory=None
        )
        declare_mock_oracle_result = await Contract.declare_v2(
            account=deployer,
            compiled_contract=compiled_oracle_mock_contract,
            compiled_contract_casm=compiled_oracle_mock_contract_casm,
            auto_estimate=True,
        )
        await declare_mock_oracle_result.wait_for_acceptance()

        # Deploy Mock Oracle
        deploy_oracle_result = await declare_mock_oracle_result.deploy_v1(
            constructor_args=[], auto_estimate=True
        )
        await deploy_oracle_result.wait_for_acceptance()
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
