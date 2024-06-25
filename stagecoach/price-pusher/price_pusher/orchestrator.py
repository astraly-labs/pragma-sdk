import logging
import asyncio

from typing import List, Optional

from pragma.core.entry import Entry, SpotEntry, FutureEntry
from pragma.core.assets import AssetType

from price_pusher.core.poller import PricePoller
from price_pusher.core.listeners.chain import PriceListener
from price_pusher.core.pusher import PricePusher
from price_pusher.type_aliases import LatestOrchestratorPairPrices


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main class responsible of the price pushing orchestration.
    """

    poller: PricePoller
    listener: PriceListener
    pusher: PricePusher
    # Contains the latest spot/future prices for each sources
    latest_prices: LatestOrchestratorPairPrices

    def __init__(
        self,
        poller: PricePoller,
        listener: PriceListener,
        pusher: PricePusher,
    ) -> None:
        # Init class properties.
        self.poller = poller
        self.listener = listener
        self.pusher = pusher

        # Contains the latest prices for each sources
        self.latest_prices: LatestOrchestratorPairPrices = {}

        # Entities communication.
        self.poller.set_update_prices_callback(self.callback_update_prices)
        self.listener.set_orchestrator_prices(self.latest_prices)

    async def run_forever(self) -> None:
        """
        Starts asynchronously the services responsible for the price updates.
        This include:
            - the poller, that fetch constantly the latest prices of all pairs
              from different sources,
            - the listener, that listen our oracle and push an event when the
              data is outdated and needs new entries,
            - the pusher, that pushes entries to our oracle.
        """
        await asyncio.gather(
            self._poller_service(),
            self._listener_service(),
            self._pusher_service(),
        )

    async def _poller_service(self) -> None:
        """
        Starts the polling service in its own thread.
        """
        while True:
            await self.poller.poll_prices()
            # Wait 10 seconds before requerying public APIs (rate limits).
            await asyncio.sleep(10)

    async def _listener_service(self) -> None:
        """
        Starts the listener service in its own thread.
        """
        while True:
            await asyncio.sleep(15)
            # TODO: implement logic
            self.listener._notify()

    async def _pusher_service(self) -> None:
        """
        Starts the pusher service in its own thread.
        This service waits for notification from the listener service and push
        all available entries.
        """
        while True:
            await self.listener.notification_event.wait()
            logger.info("💡 Notification received from the Listener! Pushing entries.")
            self.listener.notification_event.clear()
            all_latest_entries = self._flush_all_entries()
            await self.pusher.update_price_feeds(all_latest_entries)

    def _flush_all_entries(self) -> List[Entry]:
        """
        Retrieves all the available entries from our latest_prices dictionnary and
        clear them (meaning the dictionnary will be empty after this operation).
        """
        all_entries = []
        for pair_id, types in self.latest_prices.items():
            for entry_type, sources in types.items():
                for source, entry in sources.items():
                    all_entries.append(entry)
        self.latest_prices.clear()
        return all_entries

    def callback_update_prices(self, entries: List[Entry]) -> None:
        """
        Function called by the poller whenever new prices are retrieved.
        """
        for entry in entries:
            pair_id = entry.get_pair_id()
            source = entry.get_source()
            entry_type: Optional[AssetType] = (
                "SPOT"
                if isinstance(entry, SpotEntry)
                else "FUTURE"
                if isinstance(entry, FutureEntry)
                else None
            )
            if entry_type is None:
                logger.error(
                    f'Entry type of "{pair_id}" from "{source}" is unknown. Ignoring.'
                )
                continue

            if pair_id not in self.latest_prices:
                self.latest_prices[pair_id] = {}
            if entry_type not in self.latest_prices[pair_id]:
                self.latest_prices[pair_id][entry_type] = {}

            self.latest_prices[pair_id][entry_type][source] = entry
