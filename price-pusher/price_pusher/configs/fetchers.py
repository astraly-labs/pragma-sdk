from pydantic.dataclasses import dataclass
from typing import Dict, FrozenSet, List, Type

from pragma_sdk.common.fetchers.fetchers.gateio import GateioFetcher
from pragma_sdk.common.fetchers.fetchers.pyth import PythFetcher
from pragma_sdk.common.fetchers.fetchers.upbit import UpbitFetcher
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT

from pragma_sdk.common.fetchers.fetchers import (
    BitstampFetcher,
    DefillamaFetcher,
    OkxFetcher,
    HuobiFetcher,
    KrakenFetcher,
    KucoinFetcher,
    BybitFetcher,
    EkuboFetcher,
    GeckoTerminalFetcher,
    BinanceFetcher,
    LbankFetcher,
    BitgetFetcher,
    ChainlinkFetcher,
    WstETHChainlinkFetcher,
    RedstoneFetcher,
    WstETHRedstoneFetcher,
    Re7OnChainFetcher,
    USNFetcher,
    ERC4626RateFetcher,
    sUSNFetcher,
    WstETHRateFetcher,
    WstETHRateLidoFetcher,
)
from pragma_sdk.common.fetchers.future_fetchers import (
    BinanceFutureFetcher,
    ByBitFutureFetcher,
    OkxFutureFetcher,
)

ALL_SPOT_FETCHERS: List[FetcherInterfaceT] = [
    BitstampFetcher,
    KrakenFetcher,
    DefillamaFetcher,
    OkxFetcher,
    HuobiFetcher,
    KucoinFetcher,
    BybitFetcher,
    BinanceFetcher,
    EkuboFetcher,
    ChainlinkFetcher,
    WstETHChainlinkFetcher,
    RedstoneFetcher,
    WstETHRedstoneFetcher,
    Re7OnChainFetcher,
    PythFetcher,
    GateioFetcher,
    GeckoTerminalFetcher,
    # DexscreenerFetcher,
    # CoinbaseFetcher,
    UpbitFetcher,
    LbankFetcher,
    BitgetFetcher,
    USNFetcher,
    ERC4626RateFetcher,
    sUSNFetcher,
    WstETHRateFetcher,
    WstETHRateLidoFetcher,
]

# Pairs that should only be fetched by conversion rate fetchers (not market rate).
CONVERSION_RATE_ONLY_PAIRS: FrozenSet[str] = frozenset({"WSTETH/USD"})

# Fetchers that provide conversion rates (on-chain or oracle-based).
# These are NOT blocked from fetching CONVERSION_RATE_ONLY_PAIRS.
CONVERSION_RATE_FETCHERS: FrozenSet[Type[FetcherInterfaceT]] = frozenset(
    {
        ChainlinkFetcher,
        WstETHChainlinkFetcher,
        RedstoneFetcher,
        WstETHRedstoneFetcher,
        PythFetcher,
        ERC4626RateFetcher,
        sUSNFetcher,
        USNFetcher,
        Re7OnChainFetcher,
        WstETHRateFetcher,
        WstETHRateLidoFetcher,
    }
)

# Per-fetcher allowlist: a fetcher listed here ONLY fetches the given pairs
# (everything else in the config is hidden from it). Used to source a single
# illiquid asset from one specific source without activating that fetcher for
# all of its other supported assets.
# GeckoTerminal also covers the Starknet-native pairs that lost Ekubo when its
# liquidity floor went to ~$50 (dust oracle pools), so none of them loses a
# source: LORDS and NSTR go to 3, XSTRK and BROTHER/USDPLUS keep 2, SSTRK 1
# (its honest price is CONVERSION_SSTRK/USD anyway).
FETCHER_RESTRICTED_PAIRS: Dict[Type[FetcherInterfaceT], FrozenSet[str]] = {
    GeckoTerminalFetcher: frozenset(
        {
            "SURVIVOR/USD",
            "LORDS/USD",
            "NSTR/USD",
            "XSTRK/USD",
            "SSTRK/USD",
            "BROTHER/USDPLUS",
        }
    ),
}

# Per-fetcher denylist: a fetcher listed here NEVER fetches the given pairs.
# SURVIVOR/USD is excluded from Ekubo because Ekubo's on-chain PriceFetcher oracle
# reads a mispriced/stale pool for it (~$0.125 vs ~$0.038 real market, confirmed
# across every TWAP window), which would poison the published median.
# STRK/USD is excluded from Bitstamp: the strkusd market is dead (zero volume,
# `last` frozen ~30% above the market). The fetcher also rejects zero-volume
# tickers, this keeps the pair out even if a stray trade briefly revives it.
FETCHER_EXCLUDED_PAIRS: Dict[Type[FetcherInterfaceT], FrozenSet[str]] = {
    EkuboFetcher: frozenset({"SURVIVOR/USD"}),
    BitstampFetcher: frozenset({"STRK/USD"}),
}

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
