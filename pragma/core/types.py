import os
from dataclasses import dataclass
from enum import Enum, unique
from typing import List, Literal, Optional

from starknet_py.net.full_node_client import FullNodeClient

from pragma.core.utils import str_to_felt

NETWORK = os.getenv("NETWORK") or "devnet"

ADDRESS = int
HEX_STR = str

# Network Types
DEVNET = "devnet"
TESTNET = "testnet"
MAINNET = "mainnet"
SHARINGAN = "sharingan"
PRAGMA_TESTNET = "pragma_testnet"

Network = Literal["devnet", "testnet", "mainnet", "sharingan", "pragma_testnet"]

CHAIN_IDS = {
    SHARINGAN: 1536727068981429685321,
    TESTNET: 1536727068981429685321,
    MAINNET: 23448594291968334,
    PRAGMA_TESTNET: 8908953246943201047421899664489,
}

STARKSCAN_URLS = {
    MAINNET: "https://starkscan.co",
    TESTNET: "https://testnet.starkscan.co",
    DEVNET: "https://devnet.starkscan.co",
    SHARINGAN: "https://sharingan-explorer.madara.zone",
    PRAGMA_TESTNET: "https://testnet.pragmaoracle.com/explorer",
}

if not os.getenv("RPC_KEY") and NETWORK in ["mainnet", "testnet", "testnet2"]:
    raise ValueError(f"RPC_KEY env variable is required when targeting {NETWORK}")

RPC_URLS = {
    MAINNET: f"https://starknet-mainnet.infura.io/v3/{os.getenv('RPC_KEY')}",
    TESTNET: f"https://starknet-goerli.infura.io/v3/{os.getenv('RPC_KEY')}",
    DEVNET: "http://127.0.0.1:5050/rpc",
    SHARINGAN: "https://sharingan.madara.zone",
    PRAGMA_TESTNET: "https://testnet.pragmaoracle.com/rpc",
}

RPC_CLIENT = FullNodeClient(node_url=RPC_URLS[NETWORK])

AssetType = Literal["SPOT", "FUTURE", "OPTION"]


def get_client_from_network(network: str) -> FullNodeClient:
    return FullNodeClient(node_url=RPC_URLS[network])


@dataclass
class ContractAddresses:
    publisher_registry_address: int
    oracle_proxy_address: int


@unique
class AggregationMode(Enum):
    MEDIAN = "Median"
    AVERAGE = "Mean"
    ERROR = "Error"

    def serialize(self):
        return {self.value: None}


class Currency:
    id: int
    decimals: int
    is_abstract_currency: int
    starknet_address: int
    ethereum_address: int

    def __init__(
        self,
        id,
        decimals,
        is_abstract_currency,
        starknet_address=None,
        ethereum_address=None,
    ):
        if type(id) == str:
            id = str_to_felt(id)
        self.id = id

        self.decimals = decimals

        if type(is_abstract_currency) == bool:
            is_abstract_currency = int(is_abstract_currency)
        self.is_abstract_currency = is_abstract_currency

        if starknet_address is None:
            starknet_address = 0
        self.starknet_address = starknet_address

        if ethereum_address is None:
            ethereum_address = 0
        self.ethereum_address = ethereum_address

    def serialize(self) -> List[str]:
        return [
            self.id,
            self.decimals,
            self.is_abstract_currency,
            self.starknet_address,
            self.ethereum_address,
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "decimals": self.decimals,
            "is_abstract_currency": self.is_abstract_currency,
            "starknet_address": self.starknet_address,
            "ethereum_address": self.ethereum_address,
        }


class Pair:
    id: int
    quote_currency_id: int
    base_currency_id: int

    def __init__(self, id, quote_currency_id, base_currency_id):
        if type(id) == str:
            id = str_to_felt(id)
        self.id = id

        if type(quote_currency_id) == str:
            quote_currency_id = str_to_felt(quote_currency_id)
        self.quote_currency_id = quote_currency_id

        if type(base_currency_id) == str:
            base_currency_id = str_to_felt(base_currency_id)
        self.base_currency_id = base_currency_id

    def serialize(self) -> List[str]:
        return [self.id, self.quote_currency_id, self.base_currency_id]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "quote_currency_id": self.quote_currency_id,
            "base_currency_id": self.base_currency_id,
        }


DataTypes = Enum("DataTypes", ["SPOT", "FUTURE", "OPTION"])


class DataType:
    data_type: DataTypes
    pair_id: int
    expiration_timestamp: Optional[int]

    def __init__(self, data_type, pair_id, expiration_timestamp):
        if type(pair_id) == str:
            pair_id = str_to_felt(pair_id)
        self.pair_id = pair_id

        self.data_type = DataTypes(data_type)

    def serialize(self) -> dict:
        if self.data_type == DataTypes.SPOT:
            return {"SpotEntry": self.pair_id}
        if self.data_type == DataTypes.FUTURE:
            return {"FutureEntry": (self.pair_id, self.expiration_timestamp)}

    def to_dict(self) -> dict:
        return {
            "pair_id": self.id,
            "expiration_timestamp": self.expiration_timestamp,
            "data_type": self.data_type.name,
        }
