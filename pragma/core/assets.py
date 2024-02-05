from typing import Dict, List, Literal, Tuple, Union

from typing_extensions import TypedDict

from pragma.core.types import UnsupportedAssetError
from pragma.core.utils import key_for_asset

AssetType = Literal["SPOT", "FUTURE", "OPTION"]


class PragmaSpotAsset(TypedDict):
    type: str
    pair: Tuple[str, str]
    decimals: int


class PragmaFutureAsset(TypedDict):
    type: str
    pair: Tuple[str, str]
    expiry_timestamp: str
    decimals: int


class PragmaOnchainDetail(TypedDict):
    asset_name: str
    asset_address: str
    metric: str


class PragmaOnchainAsset(TypedDict):
    type: str
    source: str
    key: str
    detail: PragmaOnchainDetail
    decimals: int


PragmaAsset = Union[PragmaSpotAsset, PragmaOnchainAsset]


PRAGMA_ALL_ASSETS: List[PragmaAsset] = [
    {"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WBTC", "BTC"), "decimals": 8},
    {"type": "SPOT", "pair": ("WBTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BTC", "EUR"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WSTETH", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SOL", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DAI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LUSD", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("UNI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("USDT", "USD"), "decimals": 6},
    {"type": "SPOT", "pair": ("USDC", "USD"), "decimals": 6},
    {"type": "SPOT", "pair": ("MATIC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LORDS", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BTC", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ETH", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ETH", "USDT"), "decimals": 6},
    {"type": "SPOT", "pair": ("ETH", "USDC"), "decimals": 6},
    {"type": "SPOT", "pair": ("DAI", "USDC"), "decimals": 6},
    {"type": "SPOT", "pair": ("WBTC", "USDC"), "decimals": 6},
    {"type": "SPOT", "pair": ("ETH", "STRK"), "decimals": 18},
    {"type": "SPOT", "pair": ("STRK", "USD"), "decimals": 18},
]


_PRAGMA_ASSET_BY_KEY: Dict[str, PragmaSpotAsset] = {
    key_for_asset(asset): asset
    for asset in PRAGMA_ALL_ASSETS
    if asset["type"] == "SPOT"
}

_PRAGMA_FUTURE_ASSET_BY_KEY: Dict[str, PragmaFutureAsset] = {
    key_for_asset(asset): asset
    for asset in PRAGMA_ALL_ASSETS
    if asset["type"] == "FUTURE"
}

_PRAGMA_ALL_ASSET_BY_KEY: Dict[str, PragmaAsset] = {
    key_for_asset(asset): asset for asset in PRAGMA_ALL_ASSETS
}


# TODO (#000): Add support for option asset type
def get_asset_spec_for_pair_id_by_type(
    pair_id: str, asset_type: AssetType
) -> PragmaAsset:
    if asset_type == "SPOT":
        return get_spot_asset_spec_for_pair_id(pair_id)

    if asset_type == "FUTURE":
        return get_future_asset_spec_for_pair_id(pair_id)

    raise UnsupportedAssetError("Only SPOT & FUTURE are supported for now.")


def get_spot_asset_spec_for_pair_id(pair_id: str) -> PragmaSpotAsset:
    try:
        return _PRAGMA_ASSET_BY_KEY[pair_id]
    except KeyError as exception:
        raise KeyError(f"Pair ID not found {pair_id}") from exception


def get_future_asset_spec_for_pair_id(pair_id: str) -> PragmaFutureAsset:
    try:
        return _PRAGMA_FUTURE_ASSET_BY_KEY[pair_id]
    except KeyError as exception:
        raise KeyError(f"Pair ID not found {pair_id}") from exception


def get_asset_spec_for_pair_id(pair_id: str) -> PragmaAsset:
    try:
        return _PRAGMA_ALL_ASSET_BY_KEY[pair_id]
    except KeyError as exception:
        raise KeyError(f"Pair ID not found {pair_id}") from exception
