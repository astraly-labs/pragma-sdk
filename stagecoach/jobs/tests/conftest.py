import json
import os
import random
import subprocess
import time

import boto3
import pytest
from moto import mock_secretsmanager

from pragma.core import PragmaClient
from pragma.core.types import RPC_URLS
from pragma.tests.fixtures.devnet import get_available_port


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
def port() -> int:
    return get_available_port()


@pytest.fixture(scope="module")
def devnet_node(module_mocker, port) -> str:
    """
    This fixture prepares a forked katana
    client for e2e testing.

    :return: a starknet Client
    """
    rpc_url = RPC_URLS["testnet"][random.randint(0, len(RPC_URLS["testnet"]) - 1)]

    command = [
        "katana",
        "--rpc-url",
        str(rpc_url),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--accounts",  # deploys specified number of accounts
        str(1),
        "--seed",  # generates same accounts each time
        str(1),
    ]
    subprocess.Popen(command)
    time.sleep(10)
    _ = PragmaClient(f"http://127.0.0.1:{port}/rpc", chain_name="testnet")
    yield f"http://127.0.0.1:{port}"
