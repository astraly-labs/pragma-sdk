import pytest
import os

from pragma.tests.constants import (
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
    TESTNET_ACCOUNT_ADDRESS,
    TESTNET_ACCOUNT_PRIVATE_KEY,
)
from stagecoach.jobs.publishers.custom import app


@pytest.fixture
def mock_custom_env(monkeypatch):
    env_vars = {
        "PUBLISHER_PRIVATE_KEY": os.environ["PUBLISHER_PRIVATE_KEY"],
        "PUBLISHER_ADDRESS": TESTNET_ACCOUNT_ADDRESS,
        "NETWORK": "testnet",
        # default max_fee of 1e18 wei triggers a code 54 error (account balance < tx.max_fee)
        "MAX_FEE": int(1e16),
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


ASSETS = SAMPLE_ASSETS + SAMPLE_FUTURE_ASSETS


@pytest.mark.parametrize("asset", ASSETS)
def test_fetch_entries(asset):
    entries = app.fetch_entries([asset])

    assert len(entries) == 1
    assert entries[0].price == 1000000000  # 10 * 10 ** 8
    assert entries[0].volume == 0


@pytest.mark.asyncio
async def test_publish_all(mock_custom_env, devnet_node):
    result = await app.publish_all(SAMPLE_ASSETS)
    print("done!")
