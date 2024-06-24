import logging
import asyncio
from typing import List
from pragma.publisher.client import FetcherClient
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
        pair_config: Main PriceConfig configurations

    Returns:
        FetcherClient
    """
    spot_assets = get_unique_spot_assets_from_config_list(price_configs)
    future_assets = get_unique_future_assets_from_config_list(price_configs)

    await asyncio.gather(
        _add_spot_fetchers(fetcher_client, publisher_name, spot_assets),
        _add_future_fetchers(fetcher_client, publisher_name, future_assets),
    )

    return fetcher_client


async def _add_spot_fetchers(
    fetcher_client: FetcherClient, publisher_name: str, spot_assets: List
) -> None:
    fetchers = [
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
    await asyncio.gather(
        *[
            fetcher_client.add_fetcher(fetcher(spot_assets, publisher_name))
            for fetcher in fetchers
        ]
    )


async def _add_future_fetchers(
    fetcher_client: FetcherClient, publisher_name: str, future_assets: List
) -> None:
    fetchers = [
        BinanceFutureFetcher,
        ByBitFutureFetcher,
    ]
    await asyncio.gather(
        *[
            fetcher_client.add_fetcher(fetcher(future_assets, publisher_name))
            for fetcher in fetchers
        ]
    )
