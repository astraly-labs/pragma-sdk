import logging

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

    def run_forever(self) -> None:
        print("Orchestrating...")
        # main loop
        # entries_queue = queue.Queue()
        # Retrieve data from poller
        # Filter data with listener
        # if data is worth pushing
        # push filtered data with pusher
        # Drop useless entries (max queue size or used data)

    def callback_update_prices(self, entries: List[Entry]) -> None:
        """
        Function called by the poller whenever new prices are retrieved.
        """
        for entry in entries:
            pair_id = entry.pair_id
            source = entry.base.source
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
