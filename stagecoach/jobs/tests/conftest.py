import json
import subprocess
import time
import os

import boto3
import pytest
from moto import mock_secretsmanager
from starknet_py.net.client import Client

from pragma.core import PragmaClient
from pragma.publisher.fetchers import AvnuFetcher
from pragma.tests.constants import TESTNET_ACCOUNT_ADDRESS, TESTNET_ACCOUNT_PRIVATE_KEY
from pragma.tests.fixtures.devnet import get_available_port, get_compiler_manifest


@pytest.fixture
def mock_herodotus_env(monkeypatch):
    env_vars = {
        "ACCOUNT_ADDRESSES": "0xf00,0xbar",
        "SECRET_NAME": "SecretString",
        "ORIGIN_CHAIN": "GOERLI",
        "DEST_CHAIN": "STARKNET_GOERLI",
        "RPC_URL": "https://test.chain/rpc",
        "API_URL": "https://api.herodotus.cloud/",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.fixture
def mock_checkpoint_env(monkeypatch):
    env_vars = {
        "SECRET_NAME": "SecretString",
        "NETWORK": "testnet",
        "ASSETS": "eth/usd,btc/usd",
        "ASSET_TYPE": "SPOT",
        "ACCOUNT_ADDRESS": TESTNET_ACCOUNT_ADDRESS,
        "MAX_FEE": int(1e16),
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    yield


@pytest.fixture
def secrets():
    with mock_secretsmanager():
        conn = boto3.client("secretsmanager", region_name="eu-west-3")
        conn.create_secret(
            Name="SecretString",
            SecretString=json.dumps(
                {
                    "HERODOTUS_API_KEY": "mykey",
                    "PUBLISHER_PRIVATE_KEY": os.environ["PUBLISHER_PRIVATE_KEY"],
                }
            ),
        )
        yield conn


@pytest.fixture(scope="module")
def devnet_node(module_mocker) -> str:
    """
    This fixture prepares a forked starknet-dev
    client for e2e testing.

    :return: a starknet Client
    """
    port = get_available_port()
    command = [
        "poetry",
        "run",
        "starknet-devnet",
        "--fork-network",
        "alpha-goerli",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",  # deploys specified number of accounts
        str(1),
        "--seed",  # generates same accounts each time
        str(1),
        *get_compiler_manifest(),
    ]
    subprocess.Popen(command)  # pylint: disable=consider-using-with
    time.sleep(10)
    pragma_client = PragmaClient("devnet", port=port)
    module_mocker.patch.object(
        AvnuFetcher,
        "_pragma_client",
        return_value=pragma_client,
    )
    yield f"http://127.0.0.1:{port}"
