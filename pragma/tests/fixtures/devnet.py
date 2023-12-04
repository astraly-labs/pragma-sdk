"""
Taken from
https://github.com/software-mansion/starknet.py/blob/0243f05ebbefc59e1e71d4aee3801205a7783645/starknet_py/tests/e2e/contract_interaction/v1_interaction_test.py
"""

import os
from dotenv import load_dotenv

import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path
from typing import Generator, List
from pragma.tests.constants import FORK_BLOCK_NUMBER
import pytest

from pragma.core.types import RPC_URLS


load_dotenv()


def get_available_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.getsockname()[1]


def get_compiler_manifest() -> List[str]:
    """
    Load manifest-path file and return it as --cairo-compiler-manifest flag to starknet-devnet.
    To configure manifest locally, install Cairo 1 compiler https://github.com/starkware-libs/cairo
    and create manifest-path containing a path to top-level Cargo.toml file in cairo 1 compiler directory
    file from manifest-path.template.
    """
    try:
        manifest_file_path = Path(os.path.dirname(__file__)) / "../manifest-path"
        manifest = manifest_file_path.read_text("utf-8").splitlines()[0]

        return ["--cairo-compiler-manifest", manifest]
    except (IndexError, FileNotFoundError):
        return []


def start_devnet():
    devnet_port = get_available_port()

    if os.name == "nt":
        start_devnet_command = start_devnet_command_windows(devnet_port)
    else:
        start_devnet_command = start_devnet_command_unix(devnet_port)

    # pylint: disable=consider-using-with
    proc = subprocess.Popen(start_devnet_command)
    time.sleep(10)
    return devnet_port, proc


def fork_start_devnet():
    devnet_port = get_available_port()

    if os.name == "nt":
        start_devnet_command = start_fork_devnet_command_windows(devnet_port)
    else:
        start_devnet_command = start_fork_devnet_command_unix(devnet_port)
    proc = subprocess.Popen(start_devnet_command)
    time.sleep(10)
    return devnet_port, proc


def start_devnet_command_unix(devnet_port: int) -> List[str]:
    command = [
        "katana",
        "--chain-id",
        "SN_GOERLI",
        "--host",
        "127.0.0.1",
        "--port",
        str(devnet_port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
        "--disable-fee",
    ]
    return command


def start_devnet_command_windows(devnet_port: int) -> List[str]:
    return [
        "wsl",
        "katana",
        "--rpc-url",
        "127.0.0.1",
        "--port",
        str(devnet_port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
    ]


def start_fork_devnet_command_unix(devnet_port: int) -> List[str]:
    fork_network = os.getenv("FORK_NETWORK")
    rpc_url = RPC_URLS[fork_network]

    command = [
        "katana",
        "--fork-block-number",
        str(FORK_BLOCK_NUMBER),
        "--host",
        "127.0.0.1",
        "--port",
        str(devnet_port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
        "--rpc-url",
        str(rpc_url),
        "--disable-fee",
    ]
    return command


def start_fork_devnet_command_windows(devnet_port: int) -> List[str]:
    fork_network = os.getenv("FORK_NETWORK")
    rpc_url = RPC_URLS[fork_network]

    return [
        "wsl",
        "katana",
        "--fork-block-number",
        str(FORK_BLOCK_NUMBER),
        "--rpc-url",
        str(rpc_url),
        "--port",
        str(devnet_port),
        "--accounts",
        str(1),
        "--seed",
        str(1),
    ]


@pytest.fixture(scope="package")
def run_devnet() -> Generator[str, None, None]:
    """
    Runs devnet instance once per module and returns it's address.
    """
    devnet_port, proc = start_devnet()
    yield f"http://127.0.0.1:{devnet_port}"
    proc.kill()


@pytest.fixture(scope="package")
def fork_testnet_devnet() -> Generator[str, None, None]:
    """
    Runs devnet instance once per module and returns it's address.
    """
    devnet_port, proc = fork_start_devnet()
    yield f"http://127.0.0.1:{devnet_port}"
    proc.kill()
