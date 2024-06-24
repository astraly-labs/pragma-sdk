from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable
from pragma.core.entry import Entry

from pragma.publisher.client import FetcherClient

import logging

logger = logging.getLogger(__name__)

FnUpdatePrice = Callable[[List[Entry]], None]


class IPricePoller(ABC):
    fetcher_client: FetcherClient
    update_price_callback: Optional[FnUpdatePrice]

    @abstractmethod
    def set_update_callback(self, callback: FnUpdatePrice) -> None: ...

    @abstractmethod
    async def poll_prices(self) -> None: ...


class PricePoller(IPricePoller, ABC):
    def __init__(self, fetcher_client: FetcherClient) -> Dict:
        self.fetcher_client = fetcher_client
        self.update_price_callback = None

    def set_update_callback(self, callback: FnUpdatePrice) -> None:
        self.update_price_callback = callback

    async def poll_prices(self) -> List:
        if self.update_price_callback is None:
            logger.error("Cannot call poll_prices if the update callback is not set.")
            return []
        new_entries = await self.fetcher_client.fetch(
            filter_exceptions=True, return_exceptions=False, timeout_duration=20
        )
        logger.info(f"Successfully fetched {len(new_entries)} new entries!")
        self.update_price_callback(new_entries)
