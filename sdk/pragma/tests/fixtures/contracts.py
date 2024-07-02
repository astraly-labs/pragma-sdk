import pytest
import pytest_asyncio
from starknet_py.constants import FEE_CONTRACT_ADDRESS
from starknet_py.contract import Contract
from starknet_py.net.account.account import Account

from pragma.tests.constants import MAX_FEE, MOCK_COMPILED_DIR
from pragma.tests.utils import read_contract


async def declare_account(account: Account, compiled_account_contract: str) -> int:
    """
    Declares a specified account.
    """
    declare_tx = await account.sign_declare_v2_transaction(
        compiled_contract=compiled_account_contract,
        max_fee=MAX_FEE,
    )
    resp = await account.client.declare(transaction=declare_tx)
    await account.client.wait_for_tx(resp.transaction_hash)

    return resp.class_hash


@pytest_asyncio.fixture(scope="package")
async def account_with_validate_deploy_class_hash(
    pre_deployed_account_with_validate_deploy: Account,
) -> int:
    compiled_contract = read_contract(
        "account_with_validate_deploy_compiled.json", directory=MOCK_COMPILED_DIR
    )
    return await declare_account(
        pre_deployed_account_with_validate_deploy, compiled_contract
    )


@pytest.fixture(scope="package")
def fee_contract(full_node_account: Account) -> Contract:
    """
    Returns an instance of the fee contract. It is used to transfer tokens.
    """
    abi = [
        {
            "inputs": [
                {"name": "recipient", "type": "felt"},
                {"name": "amount", "type": "Uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "success", "type": "felt"}],
            "type": "function",
        },
        {
            "members": [
                {"name": "low", "offset": 0, "type": "felt"},
                {"name": "high", "offset": 1, "type": "felt"},
            ],
            "name": "Uint256",
            "size": 2,
            "type": "struct",
        },
    ]

    return Contract(
        address=FEE_CONTRACT_ADDRESS,
        abi=abi,
        provider=full_node_account,
    )
