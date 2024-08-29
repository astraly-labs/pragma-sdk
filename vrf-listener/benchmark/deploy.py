from typing import Tuple

from starknet_py.contract import Contract, DeclareResult, DeployResult
from starknet_py.net.account.account import Account

from benchmark.contracts import read_contract, FEE_TOKEN_ADDRESS


async def deploy_randomness_contracts(deployer: Account) -> (Contract, Contract, Contract):
    (
        _,  # declare randomness
        deploy_result,
        deploy_example_result,
        deploy_oracle_result,
    ) = await declare_deploy_randomness(deployer)
    return (
        deploy_result.deployed_contract,
        deploy_example_result.deployed_contract,
        deploy_oracle_result.deployed_contract,
    )


async def declare_deploy_randomness(
    deployer: Account,
) -> Tuple[DeclareResult, DeployResult, DeployResult, DeployResult]:
    compiled_contract = read_contract("pragma_Randomness.sierra.json", directory=None)
    compiled_contract_casm = read_contract("pragma_Randomness.casm.json", directory=None)

    compiled_example_contract = read_contract(
        "pragma_ExampleRandomness.sierra.json", directory=None
    )
    compiled_example_contract_casm = read_contract(
        "pragma_ExampleRandomness.casm.json", directory=None
    )

    compiled_oracle_mock_contract = read_contract("pragma_MockOracle.sierra.json", directory=None)
    compiled_oracle_mock_contract_casm = read_contract(
        "pragma_MockOracle.casm.json", directory=None
    )

    # Declare Randomness
    declare_result = await Contract.declare_v2(
        account=deployer,
        compiled_contract=compiled_contract,
        compiled_contract_casm=compiled_contract_casm,
        auto_estimate=True,
    )
    await declare_result.wait_for_acceptance()

    # Declare Randomness Example
    declare_example_result = await Contract.declare_v2(
        account=deployer,
        compiled_contract=compiled_example_contract,
        compiled_contract_casm=compiled_example_contract_casm,
        auto_estimate=True,
    )
    await declare_example_result.wait_for_acceptance()

    # Declare Mock Oracle
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

    # Deploy Randomness
    deploy_result = await declare_result.deploy_v1(
        constructor_args=[
            deployer.address,
            deployer.signer.public_key,
            int(FEE_TOKEN_ADDRESS, 16),
            deploy_oracle_result.deployed_contract.address,
        ],
        auto_estimate=True,
    )
    await deploy_result.wait_for_acceptance()

    # Deploy Randomness Example
    deploy_example_result = await declare_example_result.deploy_v1(
        constructor_args=[
            deploy_result.deployed_contract.address,
        ],
        auto_estimate=True,
    )
    await deploy_example_result.wait_for_acceptance()

    return declare_result, deploy_result, deploy_example_result, deploy_oracle_result
