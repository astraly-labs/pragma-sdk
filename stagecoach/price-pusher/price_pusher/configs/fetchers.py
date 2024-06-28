from pydantic import BaseModel
from typing import Dict, List

from pragma.publisher.types import PublisherInterfaceT

from pragma.publisher.fetchers import (
    BitstampFetcher,
    CexFetcher,
    DefillamaFetcher,
    OkxFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    BybitFetcher,
    BinanceFetcher,
    PropellerFetcher,
)

from pragma.publisher.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher

ALL_SPOT_FETCHERS: List[PublisherInterfaceT] = [
    BitstampFetcher,
    CexFetcher,
    DefillamaFetcher,
    OkxFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    BybitFetcher,
    BinanceFetcher,
    PropellerFetcher,
]

ALL_FUTURE_FETCHERS: List[PublisherInterfaceT] = [BinanceFutureFetcher, ByBitFutureFetcher]


class FetcherWithApiKeyConfig(BaseModel):
    """
    Configuration used for fetchers that may requires an API key.
    """

    env_api_key: str
    optional: bool = False


# Configuration for fetchers that may require API keys.
FETCHERS_WITH_API_KEY: Dict[PublisherInterfaceT, FetcherWithApiKeyConfig] = {
    PropellerFetcher: FetcherWithApiKeyConfig(env_api_key="PROPELLER_API_KEY"),
    DefillamaFetcher: FetcherWithApiKeyConfig(env_api_key="DEFI_LLAMA_API_KEY", optional=True),
}
