from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable
from pragma.core.entry import Entry

from pragma.publisher.client import FetcherClient

import logging

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

    def set_update_prices_callback(self, callback: FnUpdatePrices) -> None:
        self.update_prices_callback = callback

    async def poll_prices(self) -> List[Entry]:
        """
        Poll in parallel every fetchers for the required pairs and send them
        to the orchestrator using the callback function.
        The orchestrator will be responsible of handling the entries.
        """
        if self.update_prices_callback is None:
            logger.error("Cannot call poll_prices if the update callback is not set.")
            return []
        new_entries = await self.fetcher_client.fetch(
            filter_exceptions=True, return_exceptions=False, timeout_duration=20
        )
        logger.info(f"Successfully fetched {len(new_entries)} new entries!")
        self.update_prices_callback(new_entries)
