import os

import pytest

from pragma.tests.constants import (
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
)
from stagecoach.jobs.publishers.custom import app


@pytest.fixture
def mock_custom_env(monkeypatch):
    env_vars = {
        "PUBLISHER_PRIVATE_KEY": int(os.environ["PUBLISHER_PRIVATE_KEY"], 10),
        "PUBLISHER_ADDRESS": int(
            "0x0624EBFB99865079BD58CFCFB925B6F5CE940D6F6E41E118B8A72B7163FB435C", 16
        ),
        "NETWORK": "devnet",
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
async def test_publish_all(monkeypatch, mock_custom_env, devnet_node):
    monkeypatch.setenv("RPC_URL", devnet_node)
    _ = await app.publish_all(SAMPLE_ASSETS)
