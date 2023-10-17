import json
import os
import subprocess
import time

import boto3
import pytest
from moto import mock_secretsmanager

from pragma.core import PragmaClient
from pragma.publisher.fetchers import AvnuFetcher
from pragma.tests.fixtures.devnet import get_available_port, get_compiler_manifest


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
    This fixture prepares a forked starknet-dev
    client for e2e testing.

    :return: a starknet Client
    """
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
    pragma_client = PragmaClient(f"http://127.0.0.1:{port}/rpc", chain_name="testnet")
    module_mocker.patch.object(
        AvnuFetcher,
        "_pragma_client",
        return_value=pragma_client,
    )
    yield f"http://127.0.0.1:{port}"
