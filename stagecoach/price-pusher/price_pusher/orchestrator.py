import logging
import asyncio

from typing import List, Dict, Optional

from pragma.core.entry import Entry, SpotEntry, FutureEntry
from pragma.core.assets import AssetType

from price_pusher.configs.price_config import PriceConfig
from price_pusher.core.poller import PricePoller
from price_pusher.core.listeners import ChainPriceListener
from price_pusher.core.pusher import PricePusher

PairId = str
SourceName = str
LatestPairPrices = Dict[PairId, Dict[SourceName, Dict[AssetType, Entry]]]

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Main class responsible of the price pushing orchestration.

    See diagram in the README for more informations.
    """

    price_configs: List[PriceConfig]
    poller: PricePoller
    listener: ChainPriceListener
    pusher: PricePusher
    # Contains the latest price for each asset type for a pair.
    latest_prices: LatestPairPrices

    def __init__(
        self,
        price_configs: List[PriceConfig],
        poller: PricePoller,
        listener: ChainPriceListener,
        pusher: PricePusher,
    ) -> None:
        # Entities communicate via callbacks. Here, we set them.
        poller.set_update_prices_callback(self.callback_update_prices)

        # Init class properties.
        self.price_configs = price_configs
        self.poller = poller
        self.listener = listener
        self.pusher = pusher
        self.latest_prices = {}

    async def run_forever(self) -> None:
        await asyncio.gather(
            self._poll_prices_forever_task(),
            self._listen_for_signals_task(),
            self._push_prices_task(),
        )

    async def _poll_prices_forever_task(self) -> None:
        while True:
            await self.poller.poll_prices()
            print(self.latest_prices)
            await asyncio.sleep(5)

    async def _listen_for_signals_task(self) -> None:
        while True:
            await asyncio.sleep(15)
            logger.info("Listen chain/API & at some point, send signal...")
            # await self.listener.wait_for_signal()
            # self.push_event.set()

    async def _push_prices_task(self) -> None:
        while True:
            await asyncio.sleep(15)
            logger.info("At some point, push prices...")
            # await self.push_event.wait()  # Wait for the signal
            # self.push_event.clear()
            # self.pusher.push(self.latest_prices)  # Implement push logic in pusher

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
            if source not in self.latest_prices[pair_id]:
                self.latest_prices[pair_id][source] = {}

            self.latest_prices[pair_id][source][entry_type] = entry
