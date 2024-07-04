import logging
import asyncio
from typing import List
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient

from concurrent.futures import ThreadPoolExecutor
from pragma_sdk.common.fetchers.fetchers import (
    BitstampFetcher,
    BybitFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    OkxFetcher,
)
from pragma_sdk.common.fetchers.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from price_pusher.configs.price_config import (
    PriceConfig,
    get_unique_spot_pairs_from_config_list,
    get_unique_future_pairs_from_config_list,
)

logger = logging.getLogger(__name__)


async def add_all_fetchers(
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
    ]
    future_fetchers = [
        BinanceFutureFetcher,
        ByBitFutureFetcher,
    ]
    await _add_fetchers(fetcher_client, spot_fetchers, spot_pairs, publisher_name)
    await _add_fetchers(fetcher_client, future_fetchers, future_pairs, publisher_name)
    return fetcher_client


async def _add_fetchers(
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
    with ThreadPoolExecutor() as executor:
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                _add_one_fetcher,
                fetcher,
                fetcher_client,
                pairs,
                publisher_name,
            )
            for fetcher in fetchers
        ]
        await asyncio.gather(*tasks)


def _add_one_fetcher(
    fetcher: FetcherInterfaceT,
    fetcher_client: FetcherClient,
    pairs: List[Pair],
    publisher_name: str,
) -> None:
    """
    Add a single fetcher to the FetcherClient.

    Args:
        fetcher: The fetcher class to instantiate and add.
        fetcher_client: The FetcherClient to add the fetcher to.
        pairs: List of pairs for the fetcher.
        publisher_name: The name of the publisher.
    """
    # TODO: use the pragma_client inside the fetcher constructor.
    # Currently, a new client is created everytime.
    fetcher_client.add_fetcher(fetcher(pairs, publisher_name))
