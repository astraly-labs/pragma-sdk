import logging
import asyncio

from typing import List

from pragma.core.entry import Entry
from pragma.core.assets import PragmaAsset

from price_pusher.core.poller import PricePoller
from price_pusher.core.listener import PriceListener
from price_pusher.core.pusher import PricePusher
from price_pusher.type_aliases import LatestOrchestratorPairPrices
from price_pusher.utils.assets import asset_to_pair_id

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main class responsible of the price pushing orchestration.
    """

    poller: PricePoller
    listeners: List[PriceListener]
    pusher: PricePusher
    # Contains the latest spot/future prices for each sources
    latest_prices: LatestOrchestratorPairPrices
    push_queue: asyncio.Queue

    def __init__(
        self,
        poller: PricePoller,
        listeners: List[PriceListener],
        pusher: PricePusher,
    ) -> None:
        # Init class properties.
        self.poller = poller
        self.listeners = listeners
        self.pusher = pusher

        # Contains the latest prices for each sources
        self.latest_prices: LatestOrchestratorPairPrices = {}

        # Queue containing multiple list of Entries (that will get pushed)
        self.push_queue = asyncio.Queue()

        # Entities communication.
        self.poller.set_update_prices_callback(self.callback_update_prices)
        # Send a reference to the orchestration newest prices to the listeners.
        # NOTE: the listeners will never mutate the orchestrator prices. Only read.
        for listener in self.listeners:
            listener.set_orchestrator_prices(self.latest_prices)

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
            self._listener_services(),
            self._pusher_service(),
        )

    async def _poller_service(self) -> None:
        """
        Starts the polling service in its own thread.
        """
        while True:
            await self.poller.poll_prices()
            # Wait 5 seconds before requerying public APIs (rate limits).
            await asyncio.sleep(5)

    async def _listener_services(self) -> None:
        """
        Starts each listener in their own thread so they listen for prices updates
        for a group of pair.
        """
        tasks = [self._start_listener(listener) for listener in self.listeners]
        await asyncio.gather(*tasks)

    async def _start_listener(self, listener: PriceListener) -> None:
        """
        Start a listener in its own thread & listen for it in case a notification
        is pushed.
        """
        await asyncio.gather(listener.run_forever(), self._handle_listener(listener))

    async def _handle_listener(self, listener: PriceListener) -> None:
        """
        Monitor a listener in its own thread - wait for it to push an event, and
        if an event occurs, clear it and retrieves the entries that it was
        listening and push them to the push queue.
        """
        while True:
            await listener.notification_event.wait()
            assets_to_push = listener.price_config.get_all_assets()
            logger.info(
                f"💡 Notification received from LISTENER [{listener.id}] ! "
                "Sending entries into queue for: "
                f"{[asset_to_pair_id(asset) for asset in assets_to_push]}"
            )
            entries_to_push = self._flush_entries_for_assets(assets_to_push)
            await self.push_queue.put(entries_to_push)
            listener.notification_event.clear()

    async def _pusher_service(self) -> None:
        """
        Service reponsible of publishing entries that are in the queue.
        """
        while True:
            entries_to_push = await self.push_queue.get()
            await self.pusher.update_price_feeds(entries_to_push)
            self.push_queue.task_done()

    def _flush_entries_for_assets(self, assets: List[PragmaAsset]) -> List[Entry]:
        """
        Retrieves the prices for the assets that needs to be pushed & remove them from
        the latest_prices dict.
        """
        entries_to_push = []
        for asset in assets:
            pair_id = asset_to_pair_id(asset)
            if pair_id in self.latest_prices:
                for entry_type, sources in self.latest_prices[pair_id].items():
                    for source, entry in sources.items():
                        entries_to_push.append(entry)
                del self.latest_prices[pair_id]
        return entries_to_push

    def callback_update_prices(self, entries: List[Entry]) -> None:
        """
        Function called by the poller whenever new prices are retrieved.
        """
        for entry in entries:
            pair_id = entry.get_pair_id()
            source = entry.get_source()
            entry_type = entry.get_asset_type()

            if pair_id not in self.latest_prices:
                self.latest_prices[pair_id] = {}
            if entry_type not in self.latest_prices[pair_id]:
                self.latest_prices[pair_id][entry_type] = {}

            self.latest_prices[pair_id][entry_type][source] = entry
