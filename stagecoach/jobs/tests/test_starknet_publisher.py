import json
import os

import aiohttp
import pytest
from aioresponses import aioresponses

from pragma.tests.constants import (
    SAMPLE_ASSETS,
    SAMPLE_FUTURE_ASSETS,
    TESTNET_ACCOUNT_ADDRESS,
    TESTNET_ACCOUNT_PRIVATE_KEY,
)
from pragma.tests.fetcher_configs import FETCHER_CONFIGS


@pytest.fixture
def mock_starknet_publisher_env(monkeypatch):
    env_vars = {
        "SECRET_NAME": "SecretString",
        "NETWORK": "devnet",
        "SPOT_ASSETS": SAMPLE_ASSETS,
        "FUTURE_ASSETS": SAMPLE_FUTURE_ASSETS,
        "PUBLISHER": "MY_PUBLISHER",
        "PUBLISHER_ADDRESS": TESTNET_ACCOUNT_ADDRESS,
        "KAIKO_API_KEY": "some_key",
        "PAGINATION": 2,
        # default max_fee of 1e18 wei triggers a code 54 error (account balance < tx.max_fee)
        "MAX_FEE": int(1e16),
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.fixture
async def fetchers(devnet_node):
    assets = SAMPLE_ASSETS + SAMPLE_FUTURE_ASSETS

    with aioresponses(passthrough=[devnet_node]) as mocked:
        for fetcher, fetcher_config in FETCHER_CONFIGS.items():
            fetcher = fetcher_config["fetcher_class"](
                assets=assets, publisher=os.getenv("PUBLISHER")
            )
            with open(
                file=fetcher_config["mock_file"], mode="r", encoding="utf-8"
            ) as json_data:
                payload = json.load(json_data)
            for asset in assets:
                quote_asset, base_asset = asset["pair"]
                if fetcher == "AvnuFetcher":
                    url = await fetcher.format_url_async(quote_asset, base_asset)
                else:
                    url = fetcher.format_url(
                        quote_asset=quote_asset,
                        base_asset=base_asset,
                    )

                if fetcher == "TheGraphFetcher":
                    mocked.post(
                        url,
                        payload=payload[quote_asset],
                    )
                else:
                    mocked.get(
                        url,
                        payload=payload[quote_asset],
                    )

        yield mocked


def test_starknet_publisher_key(mock_starknet_publisher_env, secrets):
    from stagecoach.jobs.publishers.starknet_publisher import app

    assert app._get_pvt_key() == int(TESTNET_ACCOUNT_PRIVATE_KEY, 16)


@pytest.mark.asyncio
@pytest.mark.skip("TODO (#000): publisher failing test 🤔 contract not found")
async def test_starknet_publisher__handler(
    monkeypatch,
    mock_starknet_publisher_env,
    secrets,
    fetchers,
    devnet_node,
):
    monkeypatch.setenv("RPC_URL", f"{devnet_node}/rpc")
    from stagecoach.jobs.publishers.starknet_publisher import app

    assets = SAMPLE_ASSETS + SAMPLE_FUTURE_ASSETS

    async with aiohttp.ClientSession():
        entries = await app._handler(assets)

    assert len(entries) == 4
