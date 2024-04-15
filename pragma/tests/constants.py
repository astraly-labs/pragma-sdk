import os
import time
from pathlib import Path

from pragma.core.entry import SpotEntry
from pragma.core.types import Currency, Pair
from pragma.publisher.fetchers.index import AssetWeight

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
repo_root = find_repo_root(current_file_directory)

SUBMODULE_DIR = repo_root / "pragma-oracle"
MOCK_DIR = repo_root / "pragma/tests" / "mock"

CONTRACTS_COMPILED_DIR = SUBMODULE_DIR / "target/dev"
MOCK_COMPILED_DIR = MOCK_DIR / "compiled_contracts"
DEPLOYMENTS_DIR = SUBMODULE_DIR / "deployments"

print("Current Directory:", os.getcwd())
print("SUBMODULE_DIR:", SUBMODULE_DIR)
print("MOCK_DIR:", MOCK_DIR)
print("CONTRACTS_COMPILED_DIR:", CONTRACTS_COMPILED_DIR)

# -------------------------------- TESTNET -------------------------------------

TESTNET_ACCOUNT_PRIVATE_KEY = (
    "0x61910356c5adf66efb65ec3df5d07a6e5e6e7c8b59f15a13eda7a34c8d1ecc4"
)
TESTNET_ACCOUNT_ADDRESS = (
    "0x59083382aadec25d7616a7f48942d72d469b0ac581f2e935ec26b68f66bd600"
)
# 0x61910356c5adf66efb65ec3df5d07a6e5e6e7c8b59f15a13eda7a34c8d1ecc4
FEE_TOKEN_ADDRESS = "0x49d36570d4e46f48e99674bd3fcc84644ddd6b96f7c741b1562b82f9e004dc7"

# -------------------------------- INTEGRATION ---------------------------------

INTEGRATION_ACCOUNT_PRIVATE_KEY = "0x1234"

INTEGRATION_ACCOUNT_ADDRESS = (
    "0x4321647559947e9109acecb329e57594bcc3981a6118bbbfeaa9f698874bcd5"
)

INTEGRATION_NODE_URL = "http://188.34.188.184:9545/rpc/v0.4"

INTEGRATION_GATEWAY_URL = "https://external.integration.starknet.io"

PREDEPLOYED_EMPTY_CONTRACT_ADDRESS = (
    "0x0751cb46C364E912b6CB9221A857D8f90B1F6995A0e902997df774631432970E"
)

PREDEPLOYED_MAP_CONTRACT_ADDRESS = (
    "0x05cd21d6b3952a869fda11fa9a5bd2657bd68080d3da255655ded47a81c8bd53"
)

# -----------------------------------------------------------------------------

DEVNET_PRE_DEPLOYED_ACCOUNT_ADDRESS = (
    "0x4d75495e10ee26cae76478b6e491646ff0a10e0a062db1555131e47b07b7d24"
)
DEVNET_PRE_DEPLOYED_ACCOUNT_PRIVATE_KEY = (
    "0x100801800000000310080180000000010030000000000005106801800206800"
)

MAX_FEE = int(1e16)

CURRENCIES = [
    Currency("USD", 8, True, 0, 0),
    Currency(
        "BTC",
        8,
        True,
        0,
        0,
    ),
    Currency(
        "WBTC",
        8,
        False,
        0x03FE2B97C1FD336E750087D68B9B867997FD64A2661FF3CA5A7C771641E8E7AC,
        0x2260FAC5E5542A773AA44FBCFEDF7C193BC2C599,
    ),
    Currency(
        "ETH",
        18,
        False,
        0x049D36570D4E46F48E99674BD3FCC84644DDD6B96F7C741B1562B82F9E004DC7,
        0x0000000000000000000000000000000000000000,
    ),
    Currency(
        "USDC",
        6,
        False,
        0x053C91253BC9682C04929CA02ED00B3E423F6710D2EE7E0D5EBB06F3ECF368A8,
        0xA0B86991C6218B36C1D19D4A2E9EB0CE3606EB48,
    ),
    Currency(
        "USDT",
        6,
        False,
        0x068F5C6A61780768455DE69077E07E89787839BF8166DECFBF92B645209C0FB8,
        0xDAC17F958D2EE523A2206206994597C13D831EC7,
    ),
    Currency(
        "DAI",
        18,
        False,
        0x001108CDBE5D82737B9057590ADAF97D34E74B5452F0628161D237746B6FE69E,
        0x6B175474E89094C44DA98B954EEDEAC495271D0F,
    ),
]

PAIRS = [
    Pair("ETH/USD", "ETH", "USD"),
    Pair("BTC/USD", "BTC", "USD"),
    Pair("WBTC/USD", "WBTC", "USD"),
    Pair("USDC/USD", "USDC", "USD"),
    Pair("USDT/USD", "USDT", "USD"),
    Pair("DAI/USD", "DAI", "USD"),
    Pair("WBTC/USDC", "WBTC", "BTC"),
    Pair("ETH/USDC", "ETH", "USDC"),
    Pair("DAI/USDC", "DAI", "USDC"),
]

SAMPLE_ASSETS = [
    {"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "USD"), "decimals": 8},
    {"type": "INDEX", "pair": ("DPI", "USD"), "decimals": 8},
]

STARKNET_SAMPLE_ASSETS = [
    {"type": "SPOT", "pair": ("ETH", "USDC"), "decimals": 8},
    {"type": "SPOT", "pair": ("DAI", "USDC"), "decimals": 8},
    {"type": "SPOT", "pair": ("WBTC", "USDC"), "decimals": 8},
]

STARKNET_ONCHAIN_ASSETS = [
    {"type": "SPOT", "pair": ("STRK", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "STRK"), "decimals": 8},
]

SAMPLE_FUTURE_ASSETS = [
    {"type": "FUTURE", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ETH", "USD"), "decimals": 8},
]

SAMPLE_ONCHAIN_ASSETS = [
    {"type": "SPOT", "pair": ("LUSD", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WBTC", "USD"), "decimals": 8},
]
ORACLE_DECIMALS = 8
ORACLE_FEE_PRICE = 100000000000
MAX_PREMIUM_FEE = 100000000
ESTIMATED_FEE_MULTIPLIER = 1.5
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
SAMPLE_ASSET_WEIGHTS = [
    [
        AssetWeight(
            asset={"type": "SPOT", "pair": ("ETH", "USD"), "decimals": 8},
            weight=0.5,
        ),
        AssetWeight(
            asset={"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 8},
            weight=0.5,
        ),
    ],
    [
        AssetWeight(
            asset={"type": "SPOT", "pair": ("ETH", "USD"), "decimals": 10},
            weight=0.5,
        ),
        AssetWeight(
            asset={"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 6},
            weight=0.5,
        ),
    ],
]
