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

PRAGMA_SPOT_ASSETS: List[PragmaSpotAsset] = [
    {"type": "SPOT", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WBTC", "BTC"), "decimals": 8},
    {"type": "SPOT", "pair": ("WBTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BTC", "EUR"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WSTETH", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("STETH", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SOL", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DAI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LUSD", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("UNI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("USDT", "USD"), "decimals": 6},
    {"type": "SPOT", "pair": ("USDC", "USD"), "decimals": 6},
    {"type": "SPOT", "pair": ("MATIC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("NSTR", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LORDS", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "USDC"), "decimals": 6},
    {"type": "SPOT", "pair": ("DAI", "USDC"), "decimals": 6},
    {"type": "SPOT", "pair": ("WBTC", "USDC"), "decimals": 6},
    {"type": "SPOT", "pair": ("ETH", "STRK"), "decimals": 18},
    {"type": "SPOT", "pair": ("STRK", "USDT"), "decimals": 8},
    {"type": "SPOT", "pair": ("BTC", "USDT"), "decimals": 6},
    {"type": "SPOT", "pair": ("STRK", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BTC", "ETH"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "LORDS"), "decimals": 8},
    {"type": "SPOT", "pair": ("ZEND", "USDT"), "decimals": 8},
    {"type": "SPOT", "pair": ("ZEND", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ZEND", "USDC"), "decimals": 8},
    {"type": "SPOT", "pair": ("LDO", "USDT"), "decimals": 8},
    {"type": "SPOT", "pair": ("LDO", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("MKR", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("AAVE", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SNX", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("RPL", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("COMP", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("YFI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BAL", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETH", "ZEND"), "decimals": 8},
    {"type": "SPOT", "pair": ("MC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("RNDR", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("FET", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("IMX", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("GALA", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ILV", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("APE", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SAND", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("AXS", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("MANA", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ENS", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BLUR", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DPI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("MVI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DOGE", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BNB", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("XRP", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WIF", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("NEAR", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("AVAX", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LTC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("TRX", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ADA", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("LINK", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("BCH", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ARB", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("WLD", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("OP", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("DOT", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ONDO", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SUI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ETC", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ATOM", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("FIL", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("FTM", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("ORDI", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("APT", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("JUP", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("TIA", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("INJ", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("PENDLE", "USD"), "decimals": 8},
    {"type": "SPOT", "pair": ("SEI", "USD"), "decimals": 8},
]

PRAGMA_FUTURE_ASSETS: List[PragmaFutureAsset] = [
    {"type": "FUTURE", "pair": ("BTC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BTC", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ETH", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ETH", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("SOL", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("SOL", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("DOGE", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("DOGE", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("BNB", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BNB", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("XRP", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("XRP", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("1000PEPE", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("1000PEPE", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("WIF", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("WIF", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("NEAR", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("NEAR", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("AVAX", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("AVAX", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("LTC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("LTC", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("TRX", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("TRX", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ADA", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ADA", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("LINK", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("LINK", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("BCH", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("BCH", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("MATIC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("MATIC", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ARB", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ARB", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("WLD", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("WLD", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("OP", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("OP", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("DOT", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("DOT", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ONDO", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ONDO", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("SUI", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("SUI", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ETC", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ETC", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ATOM", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ATOM", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("FIL", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("FIL", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("FTM", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("FTM", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("ORDI", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("ORDI", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("UNI", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("UNI", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("APT", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("APT", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("JUP", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("JUP", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("TIA", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("TIA", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("INJ", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("INJ", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("PENDLE", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("PENDLE", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("MKR", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("MKR", "USDT"), "decimals": 6},
    {"type": "FUTURE", "pair": ("SEI", "USD"), "decimals": 8},
    {"type": "FUTURE", "pair": ("SEI", "USDT"), "decimals": 6},
]

PRAGMA_ALL_ASSETS: List[PragmaAsset] = PRAGMA_SPOT_ASSETS + PRAGMA_FUTURE_ASSETS

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
