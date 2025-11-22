import asyncio
import logging
import os

from typing import Dict, List, Optional, Sequence, Set

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.interface import FetcherInterfaceT
from pragma_sdk.common.fetchers.fetchers.evm_oracle import EVMOracleFeedFetcher
from price_pusher.configs.price_config import (
    PriceConfig,
    get_unique_spot_pairs_from_config_list,
    get_unique_future_pairs_from_config_list,
)
from price_pusher.configs.fetchers import (
    ALL_FUTURE_FETCHERS,
    ALL_SPOT_FETCHERS,
    FETCHERS_WITH_API_KEY,
)

logger = logging.getLogger(__name__)


async def add_all_fetchers(
    fetcher_client: FetcherClient,
    publisher_name: str,
    price_configs: List[PriceConfig],
    evm_rpc_urls: Optional[Sequence[str]] = None,
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
    _add_fetchers(
        fetcher_client,
        ALL_SPOT_FETCHERS,
        spot_pairs,
        publisher_name,
        evm_rpc_urls,
    )

    return fetcher_client


async def _add_fetchers(
    fetcher_client: FetcherClient,
    fetchers: List[FetcherInterfaceT],
    pairs: Set[Pair],
    publisher_name: str,
    evm_rpc_urls: Optional[Sequence[str]],
) -> None:
    """
    Add multiple fetchers to the FetcherClient concurrently.

    Args:
        fetcher_client: The FetcherClient to add fetchers to.
        fetchers: List of fetcher classes to instantiate and add.
        pairs: List of pairs for the fetchers.
        publisher_name: The name of the publisher.
    """
    await asyncio.gather(
        *[
            _add_one_fetcher(
                fetcher=fetcher,
                fetcher_client=fetcher_client,
                pairs=pairs,
                publisher_name=publisher_name,
                evm_rpc_urls=evm_rpc_urls,
            )
            for fetcher in fetchers
        ]
    )


async def _add_one_fetcher(
    fetcher: FetcherInterfaceT,
    fetcher_client: FetcherClient,
    pairs: Set[Pair],
    publisher_name: str,
    evm_rpc_urls: Optional[Sequence[str]],
):
    init_args = [list(pairs), publisher_name]
    init_kwargs: Dict[str, object] = {}

    if isinstance(fetcher, type) and issubclass(fetcher, EVMOracleFeedFetcher):
        if evm_rpc_urls:
            init_kwargs["rpc_urls"] = list(evm_rpc_urls)

    config = FETCHERS_WITH_API_KEY.get(fetcher, None)
    if config is None:
        fetcher_client.add_fetcher(fetcher(*init_args, **init_kwargs))
        return

    api_key = os.getenv(config.env_api_key)
    if api_key or config.optional:
        fetcher_client.add_fetcher(fetcher(*init_args, api_key=api_key, **init_kwargs))
    else:
        logger.warning(
            f"⚠️ API key for {fetcher.__name__} is missing. "
            f"You need to set {config.env_api_key} as an env variable. "
            "Skipping it."
        )
