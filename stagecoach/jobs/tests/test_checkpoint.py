import os

import pytest
from starknet_py.net.client_models import TransactionType

from pragma.tests.constants import TESTNET_ACCOUNT_ADDRESS


@pytest.fixture
def mock_checkpoint_env(monkeypatch):
    env_vars = {
        "SECRET_NAME": "SecretString",
        "NETWORK": "testnet",
        "ASSETS": "eth/usd,btc/usd",
        "ASSET_TYPE": "SPOT",
        "ACCOUNT_ADDRESS": TESTNET_ACCOUNT_ADDRESS,
        # default max_fee of 1e18 wei triggers a code 54 error (account balance < tx.max_fee)
        "MAX_FEE": int(1e16),
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


def test_checkpoint_get_api_key(mock_checkpoint_env, secrets):
    from stagecoach.jobs.publishers.checkpoint import app

    assert app._get_pvt_key() == int(os.environ["PUBLISHER_PRIVATE_KEY"], 10)


@pytest.mark.asyncio
async def test_checkpoint__handler(mock_checkpoint_env, secrets, devnet_node):
    from stagecoach.jobs.publishers.checkpoint import app

    invocation = await app._handler(
        [{"pair": ["eth", "usd"], "type": "SPOT"}],
    )

    assert isinstance(invocation.hash, int)
    assert (
        invocation.contract.address
        == 2771562156282025154643998054480061423405497639137376305590169894519994140346
    )
    assert invocation.invoke_transaction.calldata == [
        1,
        2771562156282025154643998054480061423405497639137376305590169894519994140346,
        1103841144918054905755429169282913006571647074466067802497666364331411604693,
        0,
        4,
        4,
        1,
        0,
        19514442401534788,
        0,
    ]
    assert invocation.invoke_transaction.type == TransactionType.INVOKE


def test_checkpoint_handler(mock_checkpoint_env, secrets, devnet_node):
    from stagecoach.jobs.publishers.checkpoint import app

    actual = app.handler(None, None)
    assert isinstance(actual["result"], int)
