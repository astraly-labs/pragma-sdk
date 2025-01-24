from pydantic.dataclasses import dataclass
from typing import Dict, List

from pragma_sdk.common.fetchers.fetchers.coinbase import CoinbaseFetcher
from pragma_sdk.common.fetchers.fetchers.gateio import GateioFetcher
from pragma_sdk.common.fetchers.fetchers.pyth import PythFetcher
from pragma_sdk.common.fetchers.fetchers.upbit import UpbitFetcher
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.common.fetchers.fetchers import *
from pragma_sdk.common.fetchers.future_fetchers import *

ALL_SPOT_FETCHERS: List[FetcherInterfaceT] = [
    BitstampFetcher,
    DefillamaFetcher,
    OkxFetcher,
    HuobiFetcher,
    KucoinFetcher,
    BybitFetcher,
    BinanceFetcher,
    EkuboFetcher,
    DexscreenerFetcher,
    PythFetcher,
    GateioFetcher,
    CoinbaseFetcher,
    UpbitFetcher,
]

ALL_FUTURE_FETCHERS: List[FetcherInterfaceT] = [
    BinanceFutureFetcher,
    ByBitFutureFetcher,
    OkxFutureFetcher,
]


@dataclass
class FetcherWithApiKeyConfig:
    """
    Configuration used for fetchers that may requires an API key.
    """

    env_api_key: str
    optional: bool = False


# Configuration for fetchers that may require API keys.
FETCHERS_WITH_API_KEY: Dict[FetcherInterfaceT, FetcherWithApiKeyConfig] = {
    DefillamaFetcher: FetcherWithApiKeyConfig(
        env_api_key="DEFI_LLAMA_API_KEY", optional=True
    ),
}
