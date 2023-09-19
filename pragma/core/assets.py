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
    {"type": "SPOT", "pair": ("AVAX", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DOGE", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SHIB", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DAI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("USDT", "USD"), "decimals": 6},
    {"type": "SPOT", "pair": ("USDC", "USD"), "decimals": 6},
    {"type": "SPOT", "pair": ("BUSD", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BNB", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ADA", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("XRP", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("MATIC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("AAVE", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("R", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LORDS", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BTC", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ETH", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ETH", "USDT"), "decimals": 6},
    {
        "type": "ONCHAIN",
        "source": "AAVE",
        "key": "AAVE-ON-BORROW",
        "detail": {
            "asset_name": "USD Coin",
            "asset_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb480xb53c1a33016b2dc2ff3653530bff1848a515c8c5",
            "metric": "variableBorrowRate",
        },
        "decimals": 18,
    },
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


# TODO: Add support for option asset type
def get_asset_spec_for_pair_id_by_type(
    pair_id: str, asset_type: AssetType
) -> PragmaAsset:
    if asset_type == "SPOT":
        return get_spot_asset_spec_for_pair_id(pair_id)
    elif asset_type == "FUTURE":
        return get_future_asset_spec_for_pair_id(pair_id)
    else:
        raise UnsupportedAssetError("Only SPOT & FUTURE are supported for now.")


def get_spot_asset_spec_for_pair_id(pair_id: str) -> PragmaSpotAsset:
    try:
        return _PRAGMA_ASSET_BY_KEY[pair_id]
    except KeyError as e:
        raise KeyError(f"Pair ID not found {pair_id}")


def get_future_asset_spec_for_pair_id(pair_id: str) -> PragmaFutureAsset:
    try:
        return _PRAGMA_FUTURE_ASSET_BY_KEY[pair_id]
    except KeyError as e:
        raise KeyError(f"Pair ID not found {pair_id}")


def get_asset_spec_for_pair_id(pair_id: str) -> PragmaAsset:
    try:
        return _PRAGMA_ALL_ASSET_BY_KEY[pair_id]
    except KeyError as e:
        raise KeyError(f"Pair ID not found {pair_id}")
