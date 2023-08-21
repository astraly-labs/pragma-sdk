import json
import os
from pathlib import Path

from starknet_py.common import create_sierra_compiled_contract

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
