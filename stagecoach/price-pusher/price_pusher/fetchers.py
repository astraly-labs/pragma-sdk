import logging
import asyncio
from typing import List, Type
from pragma.publisher.client import FetcherClient
from concurrent.futures import ThreadPoolExecutor
from pragma.publisher.fetchers import (
    BinanceFetcher,
    BitstampFetcher,
    BybitFetcher,
    CexFetcher,
    DefillamaFetcher,
    GeckoTerminalFetcher,
    HuobiFetcher,
    KucoinFetcher,
    OkxFetcher,
)
from pragma.publisher.future_fetchers import BinanceFutureFetcher, ByBitFutureFetcher
from price_pusher.configs.price_config import (
    PriceConfig,
    get_unique_spot_assets_from_config_list,
    get_unique_future_assets_from_config_list,
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
    spot_assets = get_unique_spot_assets_from_config_list(price_configs)
    future_assets = get_unique_future_assets_from_config_list(price_configs)
    spot_fetchers = [
        BitstampFetcher,
        CexFetcher,
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
    await _add_fetchers(fetcher_client, spot_fetchers, spot_assets, publisher_name)
    await _add_fetchers(fetcher_client, future_fetchers, future_assets, publisher_name)
    return fetcher_client


async def _add_fetchers(
    fetcher_client: FetcherClient,
    fetchers: List[Type],
    assets: List[str],
    publisher_name: str,
) -> None:
    """
    Add multiple fetchers to the FetcherClient.

    Args:
        fetcher_client: The FetcherClient to add fetchers to.
        fetchers: List of fetcher classes to instantiate and add.
        assets: List of assets for the fetchers.
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
                assets,
                publisher_name,
            )
            for fetcher in fetchers
        ]
        await asyncio.gather(*tasks)


def _add_one_fetcher(
    fetcher: Type, fetcher_client: FetcherClient, assets: List[str], publisher_name: str
) -> None:
    """
    Add a single fetcher to the FetcherClient.

    Args:
        fetcher: The fetcher class to instantiate and add.
        fetcher_client: The FetcherClient to add the fetcher to.
        assets: List of assets for the fetcher.
        publisher_name: The name of the publisher.
    """
    fetcher_client.add_fetcher(fetcher(assets, publisher_name))
