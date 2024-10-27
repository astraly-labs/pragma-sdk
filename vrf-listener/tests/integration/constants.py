from pathlib import Path
from typing import Dict, List, Literal

from pydantic import HttpUrl


def find_repo_root(start_directory: Path) -> Path:
    """Finds the root directory of the repo by walking up the directory tree
    and looking for a known file at the repo root.
    """
    current_directory = start_directory
    while current_directory != current_directory.parent:  # Stop at filesystem root
        if (current_directory / "pyproject.toml").is_file():
            return current_directory
        current_directory = current_directory.parent
    raise ValueError("Repository root not found!")


current_file_directory = Path(__file__).parent
repo_root = find_repo_root(current_file_directory).parent

SUBMODULE_DIR = repo_root / "pragma-oracle"
MOCK_DIR = repo_root / "pragma-sdk/tests/integration" / "mock"

CONTRACTS_COMPILED_DIR = SUBMODULE_DIR / "pragma-oracle" / "target" / "dev"
MOCK_COMPILED_DIR = MOCK_DIR / "compiled_contracts"
DEPLOYMENTS_DIR = SUBMODULE_DIR / "deployments"


U128_MAX = (1 << 128) - 1
U256_MAX = (1 << 256) - 1

NetworkName = Literal[
    "devnet",
    "mainnet",
    "sepolia",
]
Network = HttpUrl | NetworkName

RPC_URLS: Dict[Network, List[str]] = {
    "mainnet": [
        "https://starknet-mainnet.public.blastapi.io/rpc/v0_7",
        "https://rpc.starknet.lava.build:443",
        "https://free-rpc.nethermind.io/mainnet-juno",
        "https://api.cartridge.gg/x/starknet/mainnet",
    ],
    "sepolia": [
        "https://starknet-sepolia.public.blastapi.io/rpc/v0_7",
        "https://rpc.starknet-testnet.lava.build:443",
        "https://free-rpc.nethermind.io/sepolia-juno",
        "https://api.cartridge.gg/x/starknet/sepolia",
    ],
}

VRF_CONTRACT_ADDRESS = {
    "sepolia": "0x60c69136b39319547a4df303b6b3a26fab8b2d78de90b6bd215ce82e9cb515c",
    "mainnet": "0x4fb09ce7113bbdf568f225bc757a29cb2b72959c21ca63a7d59bdb9026da661",
}

EXAMPLE_VRF_USAGE_CONTRACT_ADDRESS = {
    "sepolia": "0x020be6036e52ecd3416be9ff56b1bd2c4cb610e24b60cda3b5acda4b2c8b8a41",
    "mainnet": "0x06a7b4706c0a08ce605bba1371fd4b1aa5c5d8fb243209555ec6319ce0bb2c5d",
}

VRF_ADMIN_ACCOUNT_ADDRESS = {
    "sepolia": "0x04c1d9da136846ab084ae18cf6ce7a652df7793b666a16ce46b1bf5850cc739d",
    "mainnet": "0x02356b628d108863baf8644c945d97bad70190af5957031f4852d00d0f690a77",
}

FEE_TOKEN_ADDRESS = "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7"


# ========= Accounts =============

DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS = (
    "0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201"
)
DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY = "0xc10662b7b247c7cecf7e8a30726cff12"

TESTNET_ACCOUNT_PRIVATE_KEY = "0xc10662b7b247c7cecf7e8a30726cff12"
TESTNET_ACCOUNT_ADDRESS = "0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201"
