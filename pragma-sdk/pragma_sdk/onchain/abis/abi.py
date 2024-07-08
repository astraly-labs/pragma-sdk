import json
import os
import re
from pathlib import Path

from starknet_py.common import create_sierra_compiled_contract

BUILD_DIR = Path(os.path.dirname(__file__))


def snakecase(string):
    """
    Taken from:
    https://github.com/lidatong/dataclasses-json/blob/master/dataclasses_json/stringcase.py

    Convert string into snake case.
    Join punctuation with underscore

    Args:
        string: String to convert.

    Returns:
        string: Snake cased string.

    """
    string = re.sub(r"[\-\.\s]", "_", str(string))
    if not string:
        return string
    return (string[0].lower()) + re.sub(
        r"[A-Z0-9]", lambda matched: "_" + matched.group(0).lower(), string[1:]
    )


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
    contract_compiled_sierra = Path(sierra_artifact).read_text(encoding="utf-8")
    return create_sierra_compiled_contract(
        compiled_contract=contract_compiled_sierra
    ).abi


CONTRACTS_NAMES = [
    # "pragma_Ownable",
    "pragma_Oracle",
    "pragma_PublisherRegistry",
    "pragma_SummaryStats",
    "pragma_YieldCurve",
    "pragma_Randomness",
    "pragma_ExampleRandomness",
]
ABIS = {
    contract_name: json.loads(get_abi(contract_name))
    for contract_name in CONTRACTS_NAMES
}


def get_erc20_abi():
    with open(BUILD_DIR / "pragma_ERC20.json", "r", encoding="UTF-8") as file:
        erc20_abi = json.load(file)
    return erc20_abi
