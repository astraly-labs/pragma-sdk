import time
from pathlib import Path
from typing import List

from pragma_sdk.common.fetchers.handlers.index_aggregator_handler import AssetQuantities
from pragma_sdk.common.types.entry import Pair, SpotEntry
from pragma_sdk.common.configs.asset_config import (
    ALL_ASSETS_CONFIGS,
    AssetConfig,
)
from pragma_sdk.common.types.currency import Currency
from pragma_sdk.onchain.types.types import OracleResponse

U128_MAX = (1 << 128) - 1
U256_MAX = (1 << 256) - 1


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

# -------------------------------- TESTNET -------------------------------------

TESTNET_ACCOUNT_PRIVATE_KEY = "0xc10662b7b247c7cecf7e8a30726cff12"
TESTNET_ACCOUNT_ADDRESS = (
    "0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201"
)

# 0x61910356c5adf66efb65ec3df5d07a6e5e6e7c8b59f15a13eda7a34c8d1ecc4
FEE_TOKEN_ADDRESS = "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7"

PREDEPLOYED_EMPTY_CONTRACT_ADDRESS = (
    "0x0751cb46C364E912b6CB9221A857D8f90B1F6995A0e902997df774631432970E"
)

PREDEPLOYED_MAP_CONTRACT_ADDRESS = (
    "0x05cd21d6b3952a869fda11fa9a5bd2657bd68080d3da255655ded47a81c8bd53"
)

# -----------------------------------------------------------------------------

DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS = (
    "0x260a8311b4f1092db620b923e8d7d20e76dedcc615fb4b6fdf28315b81de201"
)
DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY = "0xc10662b7b247c7cecf7e8a30726cff12"

MAX_FEE = int(1e16)

ORACLE_DECIMALS = 8
ORACLE_FEE_PRICE = 100000000000
MAX_PREMIUM_FEE = 100000000
ESTIMATED_FEE_MULTIPLIER = 3
SAMPLE_SPOT_ENTRIES = [
    SpotEntry(
        pair_id="ETH/USD",
        price=100000000000,
        volume=10000000000,
        timestamp=int(time.time()),
        source="BINANCE",
        publisher="PRAGMA_TEST",
    ),
    SpotEntry(
        pair_id="BTC/USD",
        price=300000000000,
        volume=30000000000,
        timestamp=int(time.time()),
        source="BINANCE",
        publisher="PRAGMA_TEST",
    ),
]
SAMPLE_ASSET_QUANTITIES = [
    [
        AssetQuantities(
            pair=Pair.from_tickers("ETH", "USD"),
            quantities=0.5,
        ),
        AssetQuantities(
            pair=Pair.from_tickers("BTC", "USD"),
            quantities=0.5,
        ),
    ],
    [
        AssetQuantities(
            pair=Pair.from_tickers("ETH", "USD"),
            quantities=0.5,
        ),
        AssetQuantities(
            pair=Pair.from_tickers("BTC", "USD"),
            quantities=0.5,
        ),
    ],
]

USD_ASSET_CONFIG = AssetConfig.from_ticker("USD")

CURRENCIES = [Currency.from_asset_config(asset) for asset in ALL_ASSETS_CONFIGS]
USD_PAIRS: List[Pair] = [
    Pair.from_asset_configs(asset, USD_ASSET_CONFIG)
    for asset in ALL_ASSETS_CONFIGS
    if asset != USD_ASSET_CONFIG
]

# ETH/USD, BTC/USD
SAMPLE_PAIRS = [
    Pair.from_tickers("ETH", "USD"),
    Pair.from_tickers("BTC", "USD"),
]

# LUSD/USD, WBTC/USD
ONCHAIN_SAMPLE_PAIRS = [
    Pair.from_tickers("LUSD", "USD"),
    Pair.from_tickers("WBTC", "USD"),
]

# BTC/USD, ETH/USD
SAMPLE_FUTURE_PAIRS = [
    Pair.from_tickers("BTC", "USD"),
    Pair.from_tickers("ETH", "USD"),
]

STABLE_MOCK_PRICE: OracleResponse = OracleResponse(
    price=100000000,
    decimals=8,
    last_updated_timestamp=int(time.time()),
    num_sources_aggregated=5,
    expiration_timestamp=None,
)
