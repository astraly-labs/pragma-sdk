import json
import os
from unittest import mock

import aiohttp
import pytest
from aioresponses import aioresponses

from pragma.tests.constants import (
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
)
from pragma.tests.fetcher_configs import (
    FETCHER_CONFIGS,
    FUTURE_FETCHER_CONFIGS,
    ONCHAIN_FETCHER_CONFIGS,
)


@pytest.fixture
def mock_starknet_publisher_env(monkeypatch):
    env_vars = {
        "SECRET_NAME": "SecretString",
        "NETWORK": "testnet",
        "SPOT_ASSETS": SAMPLE_ASSETS,
        "FUTURE_ASSETS": SAMPLE_FUTURE_ASSETS,
        "PUBLISHER": "PRAGMA",
        "PUBLISHER_ADDRESS": int(
            "0x0624EBFB99865079BD58CFCFB925B6F5CE940D6F6E41E118B8A72B7163FB435C", 16
        ),
        "PUBLISHER_PRIVATE_KEY": int(os.environ["PUBLISHER_PRIVATE_KEY"]),
        "KAIKO_API_KEY": "some_key",
        "PAGINATION": 40,
        # default max_fee of 1e18 wei triggers a code 54 error (account balance < tx.max_fee)
        "MAX_FEE": int(1e16),
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


def test_starknet_publisher_key(mock_starknet_publisher_env, secrets):
    from stagecoach.jobs.publishers.starknet_publisher import app

    assert app._get_pvt_key() == int(os.environ["PUBLISHER_PRIVATE_KEY"], 0)


@mock.patch("time.time", mock.MagicMock(return_value=12345))
@pytest.mark.asyncio
async def test_starknet_publisher__handler(
    monkeypatch,
    mock_starknet_publisher_env,
    secrets,
    devnet_node,
):
    monkeypatch.setenv("RPC_URL", devnet_node)
    from stagecoach.jobs.publishers.starknet_publisher import app

    # TODO: maybe move these into a fixture?
    fetcher_configs = {
        **FETCHER_CONFIGS,
        **FUTURE_FETCHER_CONFIGS,
        **ONCHAIN_FETCHER_CONFIGS,
    }

    assets = SAMPLE_ASSETS + SAMPLE_FUTURE_ASSETS

    # TODO: refactor this cos it's ugly
    with aioresponses(passthrough=[devnet_node]) as mocked:
        for fetcher, fetcher_config in fetcher_configs.items():
            fetcher = fetcher_config["fetcher_class"](
                assets=assets, publisher=os.getenv("PUBLISHER")
            )
            with open(
                file=fetcher_config["mock_file"], mode="r", encoding="utf-8"
            ) as json_data:
                payload = json.load(json_data)
                for asset in assets:
                    quote_asset, base_asset = asset["pair"]
                    url = fetcher.format_url(quote_asset, base_asset)

                    mocked.get(
                        url,
                        status=200,
                        payload=payload.get(quote_asset),
                    )

        async with aiohttp.ClientSession():
            entries = await app._handler(assets)

        assert len(entries) == 4
