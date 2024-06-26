import logging

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable

from pragma.core.entry import Entry
from pragma.publisher.client import FetcherClient

from price_pusher.utils.retries import retry_async

logger = logging.getLogger(__name__)

FnUpdatePrices = Callable[[List[Entry]], None]


class IPricePoller(ABC):
    fetcher_client: FetcherClient
    update_prices_callback: Optional[FnUpdatePrices]

    @abstractmethod
    def set_update_prices_callback(self, callback: FnUpdatePrices) -> None: ...

    @abstractmethod
    async def poll_prices(self) -> None: ...


class PricePoller(IPricePoller):
    def __init__(self, fetcher_client: FetcherClient) -> Dict:
        self.fetcher_client = fetcher_client
        self.update_prices_callback = None

    @property
    def is_requesting_onchain(self) -> bool:
        self.fetcher_client.fetchers[0].client.full_node_client is not None

    def set_update_prices_callback(self, callback: FnUpdatePrices) -> None:
        self.update_prices_callback = callback

    async def poll_prices(self) -> None:
        """
        Poll in parallel every fetchers for the required pairs and send them
        to the orchestrator using the callback function.
        The orchestrator will be responsible of handling the entries.
        """
        if self.update_prices_callback is None:
            logger.error("Cannot call poll_prices if the update callback is not set.")
            return []

        async def fetch_action():
            new_entries = await self.fetcher_client.fetch(
                filter_exceptions=True, return_exceptions=False, timeout_duration=20
            )
            return new_entries

        try:
            new_entries = await fetch_action()
            logger.info(f"Successfully fetched {len(new_entries)} new entries!")
            self.update_prices_callback(new_entries)
        except Exception as e:
            if self.is_requesting_onchain():
                try:
                    logger.warning("🤔 Fetching on chain prices failed. Retrying...")
                    new_entries = await retry_async(fetch_action, retries=5, delay_in_s=5)
                    self.update_prices_callback(new_entries)
                except Exception as e:
                    raise ValueError(f"Retries for polling new prices still failed: {e}")
            else:
                raise e
