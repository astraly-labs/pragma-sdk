import asyncio
import logging

from abc import ABC, abstractmethod
from typing import Optional

from pragma.core.entry import Entry
from pragma.core.assets import AssetType

from price_pusher.configs import PriceConfig
from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.type_aliases import (
    DurationInSeconds,
    LatestOrchestratorPairPrices,
    HumanReadableId,
)
from price_pusher.utils.assets import asset_to_pair_id
from price_pusher.utils.readable_id import generate_human_readable_id
from pragma.publisher.client import PragmaAPIError


logger = logging.getLogger(__name__)


class IPriceListener(ABC):
    """
    Sends a signal to the Orchestrator when we need to update prices.
    """

    id: HumanReadableId

    request_handler: IRequestHandler
    price_config: PriceConfig

    orchestrator_prices: Optional[LatestOrchestratorPairPrices]

    notification_event: asyncio.Event
    polling_frequency_in_s: DurationInSeconds

    @abstractmethod
    def set_orchestrator_prices(
        self, orchestrator_prices: LatestOrchestratorPairPrices
    ) -> None: ...

    @abstractmethod
    async def run_forever(self) -> None: ...

    @abstractmethod
    async def _fetch_all_oracle_prices(self) -> None: ...

    @abstractmethod
    def _get_most_recent_orchestrator_entry(
        self, pair_id: str, asset_type: AssetType
    ) -> Optional[Entry]: ...

    @abstractmethod
    def _notify(self) -> None: ...

    @abstractmethod
    def _log_listener_spawning(self) -> None: ...

    @abstractmethod
    async def _does_oracle_needs_update(self) -> bool: ...

    @abstractmethod
    def _new_price_is_deviating(self, pair_id: str, new_price: int, oracle_price: int) -> bool: ...

    @abstractmethod
    def _oracle_entry_is_outdated(
        self, pair_id: str, oracle_entry: Entry, newest_entry: Entry
    ) -> bool: ...


class PriceListener(IPriceListener):
    def __init__(
        self,
        request_handler: IRequestHandler,
        price_config: PriceConfig,
        polling_frequency_in_s: DurationInSeconds,
    ) -> None:
        self.id = generate_human_readable_id()
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
                last_fetch_time = -1
            await asyncio.sleep(0.1)

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
            self.request_handler.fetch_latest_entry(asset)
            for asset in self.price_config.get_all_assets()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for entry in results:
            if isinstance(entry, Exception) or isinstance(entry, PragmaAPIError):
                logger.error(f"Error fetching oracle price: {entry}")
                continue
            if entry is None:
                continue

            pair_id = entry.get_pair_id().replace(",", "/")
            asset_type = entry.get_asset_type()

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
        if pair_id not in self.orchestrator_prices:
            return None
        entries = [entry for entry in self.orchestrator_prices[pair_id][asset_type].values()]
        return max(entries, key=lambda entry: entry.get_timestamp(), default=None)

    async def _does_oracle_needs_update(self) -> bool:
        """
        Return if the oracle prices needs an update.

        To know if they need we check:
            - if the latest entry found in our oracle is too old,
            - if the price deviated too much with the prices fetched from the poller
        """
        if self.orchestrator_prices is None:
            raise ValueError("Orchestrator must set the prices dictionnary.")

        if len(self.orchestrator_prices.keys()) == 0:
            return False

        if len(self.oracle_prices.keys()) == 0:
            logging.error(
                f"LISTENER {self.id} have no oracle prices at all... Sending notification."
            )
            return True

        for pair_id, oracle_entries in self.oracle_prices.items():
            if pair_id not in self.orchestrator_prices:
                continue
            for asset_type, orchestrator_entries in self.orchestrator_prices[pair_id].items():
                if asset_type not in oracle_entries:
                    logging.warn(
                        f"LISTENER {self.id} miss prices in oracle entries. Sending notification."
                    )
                    return True
                oracle_entry = oracle_entries[asset_type]

                # First check if the oracle entry is outdated
                newest_entry = self._get_most_recent_orchestrator_entry(pair_id, asset_type)
                if self._oracle_entry_is_outdated(pair_id, oracle_entry, newest_entry):
                    return True

                # If not, check its deviation
                for entry in orchestrator_entries.values():
                    if self._new_price_is_deviating(pair_id, entry.price, oracle_entry.price):
                        return True
        return False

    def _new_price_is_deviating(self, pair_id: str, new_price: int, oracle_price: int) -> bool:
        """
        Check if a new price is in the bounds allowed by the configuration.
        """
        max_deviation = self.price_config.price_deviation * oracle_price
        is_deviating = abs(new_price - oracle_price) >= max_deviation
        if is_deviating:
            # TODO: show current deviation
            logger.info(
                f"🔔 Newest price for {pair_id} is deviating from the "
                "config bounds. Triggering an update!"
            )
        return is_deviating

    def _oracle_entry_is_outdated(
        self, pair_id: str, oracle_entry: Entry, newest_entry: Entry
    ) -> bool:
        """
        Check if the newest entry is recent enough to trigger an update.
        We do that by checking the difference between the most recent entry from
        the orchestrator and the most recent entry for the oracle.
        """
        max_time_elapsed = self.price_config.time_difference

        delta_t = newest_entry.get_timestamp() - oracle_entry.get_timestamp()
        is_outdated = delta_t > max_time_elapsed

        if is_outdated:
            # TODO: show time diff
            logger.info(f"🔔 Last oracle entry for {pair_id} is too old. " "Triggering an update!")

        return is_outdated

    def _notify(self) -> None:
        """
        Sends a notification.
        """
        logger.info(f"🏓 LISTENER [{self.id}] sending notification to the Orchestrator!")
        self.notification_event.set()

    def _log_listener_spawning(self) -> None:
        """
        Logs that a thread has been successfuly spawned for this listener.
        """
        assets = self.price_config.get_all_assets()
        pairs = [asset_to_pair_id(asset) for asset in assets]
        logging.info(f"👂 Spawned listener [{self.id}] for pairs: {pairs}")
