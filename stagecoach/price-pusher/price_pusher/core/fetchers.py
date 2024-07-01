import logging
import asyncio
import os

from typing import List
from concurrent.futures import ThreadPoolExecutor

from pragma.publisher.client import FetcherClient
from pragma.publisher.types import PublisherInterfaceT

from price_pusher.configs.fetchers import (
    ALL_SPOT_FETCHERS,
    ALL_FUTURE_FETCHERS,
    FETCHERS_WITH_API_KEY,
)
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
    await _add_fetchers(fetcher_client, ALL_SPOT_FETCHERS, spot_assets, publisher_name)
    await _add_fetchers(fetcher_client, ALL_FUTURE_FETCHERS, future_assets, publisher_name)
    return fetcher_client


async def _add_fetchers(
    fetcher_client: FetcherClient,
    fetchers: List[PublisherInterfaceT],
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
    fetcher: PublisherInterfaceT,
    fetcher_client: FetcherClient,
    assets: List[str],
    publisher_name: str,
) -> None:
    """
    Add a single fetcher to the FetcherClient.

    Args:
        fetcher: The fetcher class to instantiate and add.
        fetcher_client: The FetcherClient to add the fetcher to.
        assets: List of assets for the fetcher.
        publisher_name: The name of the publisher.
    """
    config = FETCHERS_WITH_API_KEY.get(fetcher, None)
    if config is None:
        fetcher_client.add_fetcher(fetcher(assets, publisher_name))
        return

    api_key = os.getenv(config.env_api_key)
    if api_key or config.optional:
        fetcher_client.add_fetcher(fetcher(assets, publisher_name, api_key))
    else:
        logger.warning(
            f"⚠️ API key for {fetcher.__name__} is missing. "
            f"Please set {config.env_api_key} as an env variable. "
            "Skipping it for now."
        )
        return
