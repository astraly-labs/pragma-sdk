import asyncio
import logging

from abc import ABC, abstractmethod
from typing import Optional

from pragma.core.entry import Entry, SpotEntry
from pragma.core.assets import AssetType

from price_pusher.configs import PriceConfig
from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.type_aliases import (
    DurationInSeconds,
    LatestOrchestratorPairPrices,
    LatestOraclePairPrices,
)
from price_pusher.utils.assets import asset_to_pair_id

logger = logging.getLogger(__name__)


class IPriceListener(ABC):
    """
    Sends a signal to the Orchestrator when we need to update prices.
    """

    request_handler: IRequestHandler
    price_config: PriceConfig

    oracle_prices: LatestOraclePairPrices
    orchestrator_prices: Optional[LatestOrchestratorPairPrices]

    notification_event: asyncio.Event
    polling_frequency_in_s: DurationInSeconds

    @abstractmethod
    def _log_listener_spawning(self) -> None: ...

    @abstractmethod
    async def _fetch_all_oracle_prices(self) -> None: ...

    @abstractmethod
    def _get_most_recent_orchestrator_entry(
        self, pair_id: str, asset_type: AssetType
    ) -> Optional[Entry]: ...

    @abstractmethod
    async def _does_oracle_needs_update(self) -> bool: ...

    @abstractmethod
    def _notify(self) -> None: ...

    @abstractmethod
    def set_orchestrator_prices(
        self, orchestrator_prices: LatestOrchestratorPairPrices
    ) -> None: ...

    @abstractmethod
    async def run_forever(self) -> None: ...


class PriceListener(IPriceListener):
    def __init__(
        self,
        request_handler: IRequestHandler,
        price_config: PriceConfig,
        polling_frequency_in_s: DurationInSeconds,
    ) -> None:
        self.request_handler = request_handler
        self.price_config = price_config

        self.oracle_prices = {}
        self.orchestrator_prices = None

        self.notification_event = asyncio.Event()
        self.polling_frequency_in_s = polling_frequency_in_s

        self._log_listener_spawning()

    async def run_forever(self) -> None:
        """
        Main loop responsible of:
            - fetching the latest oracle prices
            - checking if the oracle needs update
            - pushing notification to the orchestration if it does.
        """
        last_fetch_time = -1
        while True:
            current_time = asyncio.get_event_loop().time()
            if current_time - last_fetch_time >= self.polling_frequency_in_s:
                await self._fetch_all_oracle_prices()
                last_fetch_time = current_time
            if await self._does_oracle_needs_update():
                self._notify()
            # Check every second if the oracle needs an update
            await asyncio.sleep(1)

    def set_orchestrator_prices(self, orchestrator_prices: dict) -> None:
        """
        Set the reference of the orchestrator prices in the Listener.
        """
        self.orchestrator_prices = orchestrator_prices

    async def _fetch_all_oracle_prices(self) -> None:
        """
        Fetch the latest oracle prices for all assets in parallel.
        """
        tasks = [
            self.request_handler.fetch_latest_asset_price(asset)
            for asset in self.price_config.get_all_assets()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for entry in results:
            if isinstance(entry, Exception):
                logger.error(f"Error fetching oracle price: {entry}")
                continue
            if entry is None:
                continue

            pair_id = entry.get_pair_id().replace(",", "/")
            asset_type = "SPOT" if isinstance(entry, SpotEntry) else "FUTURE"

            if pair_id not in self.oracle_prices:
                self.oracle_prices[pair_id] = {}

            self.oracle_prices[pair_id][asset_type] = entry

    def _get_most_recent_orchestrator_entry(
        self, pair_id: str, asset_type: AssetType
    ) -> Optional[Entry]:
        """
        Retrieves the latest registered entry from the orchestrator prices.
        """
        if self.orchestrator_prices is None:
            raise ValueError("Orchestrator must set the prices dictionnary.")
        entries = [
            entry for entry in self.orchestrator_prices[pair_id][asset_type].values()
        ]
        return max(entries, key=lambda entry: entry.base.timestamp, default=None)

    async def _does_oracle_needs_update(self) -> bool:
        """
        Compare the oracle prices with our orchestrator fetched prices from sources.
        If some conditions are met, we return true, else false, meaning that we
        can send a notification to the orchestrator.
        """
        if self.orchestrator_prices is None:
            raise ValueError("Orchestrator must set the prices dictionnary.")
        if len(self.orchestrator_prices.keys()) == 0:
            return False
        
        for pairid, oracle_value in self.oracle_prices.items():
            for asset_type, datas in self.orchestrator_prices[pairid].items():
                for _,entry in datas.items():
                    if self._is_in_deviation_bounds(entry.price, oracle_value[asset_type].price) :
                        return True
                    delta_t = entry.base.timestamp - self._get_most_recent_orchestrator_entry(pairid,asset_type).base.timestamp
                    if  delta_t > self.price_config.time_difference:
                        return True

        return False

    def _is_in_deviation_bounds(self, price: int, ref_price: int) -> bool:
        max_deviation = (self.price_config.price_deviation / 100) * ref_price
        
        lower_bound = ref_price - max_deviation
        upper_bound = ref_price + max_deviation
        
        return lower_bound <= price <= upper_bound

    def _notify(self) -> None:
        """
        Sends a notification.
        """
        logger.info("🏓 Sending notification to the Orchestrator!")
        self.notification_event.set()

    def _log_listener_spawning(self) -> None:
        """
        Logs that a thread has been successfuly spawned for this listener.
        """
        assets = self.price_config.get_all_assets()
        pairs = [asset_to_pair_id(asset) for asset in assets]
        logging.info(f"👂 Spawned a listener for pairs: {pairs}")
