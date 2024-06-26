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

        # If we're requesting some onchain fetchers, we allow for requests
        # retry in case of a small RPC down time etc...
        self._is_requesting_onchain = any(
            getattr(getattr(fetcher, "client", None), "full_node_client", None) is not None
            for fetcher in self.fetcher_client.fetchers
        )

    def set_update_prices_callback(self, callback: FnUpdatePrices) -> None:
        self.update_prices_callback = callback

    async def poll_prices(self) -> None:
        """
        Poll in parallel every fetchers for the required pairs and send them
        to the orchestrator using the callback function.
        The orchestrator will be responsible of handling the entries.
        """
        if self.update_prices_callback is None:
            raise ValueError("Update callback must be set.")

        try:
            new_entries = await self._fetch_action()
            logger.info(f"POLLER successfully fetched {len(new_entries)} new entries!")
            self.update_prices_callback(new_entries)
        except Exception as e:
            if not self._is_requesting_onchain:
                raise e
            try:
                logger.warning("🤔 POLLER fetching prices failed. Retrying...")
                new_entries = await retry_async(self._fetch_action, retries=5, delay_in_s=5)
                self.update_prices_callback(new_entries)
            except Exception as e:
                raise ValueError(f"POLLERS retries for fetching new prices still failed: {e}")

    async def _fetch_action(self) -> None:
        """
        Call the fetcher client `fetch` function to try to retrieve all entries from fetchers.
        """
        new_entries = await self.fetcher_client.fetch(
            filter_exceptions=True, return_exceptions=False, timeout_duration=20
        )
        return new_entries
