import logging
from typing import List
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.fetchers import (
    BitstampFetcher,
    BybitFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    OkxFetcher,
    BinanceFetcher,
)
from pragma_sdk.common.fetchers.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from price_pusher.configs.price_config import (
    PriceConfig,
    get_unique_spot_pairs_from_config_list,
    get_unique_future_pairs_from_config_list,
)

logger = logging.getLogger(__name__)


def add_all_fetchers(
    fetcher_client: FetcherClient,
    publisher_name: str,
    price_configs: List[PriceConfig],
) -> FetcherClient:
    """
    Add fetchers to the FetcherClient based on the provided configuration.

    Args:
        fetcher_client: The FetcherClient to add fetchers to.
        publisher_name: The name of the publisher.
        price_configs: List of PriceConfig configurations.

    Returns:
        FetcherClient
    """
    spot_pairs = get_unique_spot_pairs_from_config_list(price_configs)
    future_pairs = get_unique_future_pairs_from_config_list(price_configs)
    spot_fetchers = [
        BitstampFetcher,
        DefillamaFetcher,
        OkxFetcher,
        GeckoTerminalFetcher,
        HuobiFetcher,
        KucoinFetcher,
        BybitFetcher,
        BinanceFetcher,
    ]
    future_fetchers = [
        BinanceFutureFetcher,
        ByBitFutureFetcher,
    ]
    _add_fetchers(fetcher_client, spot_fetchers, spot_pairs, publisher_name)
    _add_fetchers(fetcher_client, future_fetchers, future_pairs, publisher_name)
    return fetcher_client


def _add_fetchers(
    fetcher_client: FetcherClient,
    fetchers: List[FetcherInterfaceT],
    pairs: List[Pair],
    publisher_name: str,
) -> None:
    """
    Add multiple fetchers to the FetcherClient.

    Args:
        fetcher_client: The FetcherClient to add fetchers to.
        fetchers: List of fetcher classes to instantiate and add.
        pairs: List of pairs for the fetchers.
        publisher_name: The name of the publisher.
    """
    for fetcher in fetchers:
        fetcher_client.add_fetcher(fetcher(pairs, publisher_name))
