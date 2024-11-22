from pydantic.dataclasses import dataclass
from typing import Dict, List

from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.common.fetchers.fetchers import (
    BitstampFetcher,
    BybitFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    OkxFetcher,
    BinanceFetcher,
    EkuboFetcher,
    DexscreenerFetcher,
)
from pragma_sdk.common.fetchers.future_fetchers import (
    BinanceFutureFetcher,
    ByBitFutureFetcher,
    OkxFutureFetcher,
)


ALL_SPOT_FETCHERS: List[FetcherInterfaceT] = [
    BitstampFetcher,
    DefillamaFetcher,
    OkxFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    BybitFetcher,
    BinanceFetcher,
    EkuboFetcher,
    DexscreenerFetcher,
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
