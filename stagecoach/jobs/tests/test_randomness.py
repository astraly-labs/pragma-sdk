import pytest


@pytest.fixture
def mock_randomness_env(monkeypatch):
    env_vars = {
        "START_BLOCK": "0",
        "NETWORK": "testnet",
        "ADMIN_PRIVATE_KEY": "TESTNET_ACCOUNT_PRIVATE_KEY",
        "ADMIN_CONTRACT_ADDRESS": "TESTNET_ACCOUNT_ADDRESS",
        "VRF_CONTRACT_ADDRESS": "",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.mark.asyncio
async def test_randomness_handler(mock_randomness_env):
    from stagecoach.jobs.randomness import app

    result = await app.handler(None, None)
    assert result["success"]
