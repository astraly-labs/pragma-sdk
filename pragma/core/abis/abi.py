import json
import os
from pathlib import Path

from starknet_py.common import create_sierra_compiled_contract


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

BUILD_DIR = Path(os.path.dirname(__file__))


def get_artifact(contract_name):
    return BUILD_DIR / f"{contract_name}.json"


def get_alias(contract_name):
    return snakecase(contract_name)


def get_sierra_artifact(contract_name):
    return BUILD_DIR / f"{contract_name}.sierra.json"


def get_casm_artifact(contract_name):
    return BUILD_DIR / f"{contract_name}.casm.json"


def get_abi(contract_name):
    sierra_artifact = get_sierra_artifact(contract_name)
    contract_compiled_sierra = Path(sierra_artifact).read_text()
    return create_sierra_compiled_contract(
        compiled_contract=contract_compiled_sierra
    ).abi


CONTRACTS_NAMES = [
    "pragma_Admin",
    "pragma_Oracle",
    "pragma_PublisherRegistry",
    "pragma_SummaryStats",
    "pragma_YieldCurve",
]
ABIS = {
    contract_name: json.loads(get_abi(contract_name))
    for contract_name in CONTRACTS_NAMES
}
