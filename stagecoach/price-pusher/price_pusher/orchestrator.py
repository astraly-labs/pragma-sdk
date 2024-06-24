from typing import List
from price_pusher.configs.price_config import PriceConfig
from price_pusher.core.poller import PricePoller
from price_pusher.core.listeners import ChainPriceListener
from price_pusher.core.pusher import PricePusher


class Orchestrator:
    """
    Main class responsible of the price pushing orchestration.

    See diagram in the README for more informations.
    """

    price_configs: List[PriceConfig]
    poller: PricePoller
    listener: ChainPriceListener
    pusher: PricePusher

    def __init__(
        self,
        price_configs: List[PriceConfig],
        poller: PricePoller,
        listener: ChainPriceListener,
        pusher: PricePusher,
    ) -> None:
        self.price_configs = price_configs
        self.poller = poller
        self.listener = listener
        self.pusher = pusher

    def run_forever(self) -> None:
        print("Orchestrating...")

        # main loop
        # entries_queue = queue.Queue()
        # Retrieve data from poller
        # Filter data with listener
        # if data is worth pushing
        # push filtered data with pusher
        # Drop useless entries (max queue size or used data)
