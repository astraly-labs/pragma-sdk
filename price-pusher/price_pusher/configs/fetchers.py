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
    PropellerFetcher,
    StarknetAMMFetcher,
)
from pragma_sdk.common.fetchers.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher


ALL_SPOT_FETCHERS: List[FetcherInterfaceT] = [
    BitstampFetcher,
    DefillamaFetcher,
    OkxFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    BybitFetcher,
    BinanceFetcher,
    PropellerFetcher,
    StarknetAMMFetcher,
]

ALL_FUTURE_FETCHERS: List[FetcherInterfaceT] = [BinanceFutureFetcher, ByBitFutureFetcher]


@dataclass
class FetcherWithApiKeyConfig:
    """
    Configuration used for fetchers that may requires an API key.
    """

    env_api_key: str
    optional: bool = False


# Configuration for fetchers that may require API keys.
FETCHERS_WITH_API_KEY: Dict[FetcherInterfaceT, FetcherWithApiKeyConfig] = {
    PropellerFetcher: FetcherWithApiKeyConfig(env_api_key="PROPELLER_API_KEY"),
    DefillamaFetcher: FetcherWithApiKeyConfig(env_api_key="DEFI_LLAMA_API_KEY", optional=True),
}
