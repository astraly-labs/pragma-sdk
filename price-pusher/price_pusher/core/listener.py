import asyncio
import logging
import statistics

from abc import ABC, abstractmethod
from typing import Optional, Dict, List

from pragma_utils.readable_id import generate_human_readable_id, HumanReadableId

from pragma_sdk.common.types.entry import Entry, SpotEntry, FutureEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.types.types import DataTypes

from price_pusher.utils import exclude_none_and_exceptions, flatten_list
from price_pusher.configs import PriceConfig
from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.types import (
    DurationInSeconds,
    LatestOrchestratorPairPrices,
    ExpiryTimestamp,
    SourceName,
    FuturePrices,
)


CONSECUTIVES_EMPTY_ERRORS_LIMIT = 10
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

    consecutive_empty_oracle_error: int

    @property
    def data_config(self) -> Dict[DataTypes, List[Pair]]: ...

    @abstractmethod
    def set_orchestrator_prices(
        self, orchestrator_prices: LatestOrchestratorPairPrices
    ) -> None: ...

    @abstractmethod
    async def run_forever(self) -> None: ...

    @abstractmethod
    async def _fetch_all_oracle_prices(self) -> None: ...

    @abstractmethod
    def _get_latest_orchestrator_entry(
        self, pair_id: str, data_type: DataTypes
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

        self.consecutive_empty_oracle_error = 0

        self._log_listener_spawning()

    @property
    def data_config(self) -> Dict[DataTypes, List[Pair]]:
        return self.price_config.get_all_assets()

    async def run_forever(self) -> None:
        """
        Main loop responsible of:
            - fetching the latest oracle prices
            - checking if the oracle needs update
            - pushing notification to the orchestration if it does.
        """
        last_fetch_time = -1
        while True:
            # Check if the notification event is clear
            while self.notification_event.is_set():
                await asyncio.sleep(1)

            current_time = asyncio.get_event_loop().time()
            if current_time - last_fetch_time >= self.polling_frequency_in_s:
                await self._fetch_all_oracle_prices()
                last_fetch_time = current_time
            if await self._does_oracle_needs_update():
                self._notify()
                last_fetch_time = -1
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
            self.request_handler.fetch_latest_entries(data_type, pair)
            for data_type, pairs in self.data_config.items()
            for pair in pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        results = flatten_list(exclude_none_and_exceptions(results))

        for entry in results:
            pair_id = entry.get_pair_id().replace(",", "/")
            data_type = entry.get_asset_type()
            expiry = entry.get_expiry()

            if pair_id not in self.oracle_prices:
                self.oracle_prices[pair_id] = {}
            if data_type not in self.oracle_prices[pair_id]:
                self.oracle_prices[pair_id][data_type] = {}

            match data_type:
                case DataTypes.SPOT:
                    self.oracle_prices[pair_id][data_type] = entry
                case DataTypes.FUTURE:
                    if expiry is None:
                        logger.error(
                            f"Expiry none for future entry from Oracle: {pair_id}. Ignoring."
                        )
                        continue
                    self.oracle_prices[pair_id][data_type][expiry] = entry

    def _get_latest_orchestrator_entry(
        self, pair_id: str, data_type: DataTypes, expiry: str = None
    ) -> Optional[Entry]:
        """
        Retrieves the latest registered entry from the orchestrator prices.
        """
        if self.orchestrator_prices is None:
            raise ValueError("Orchestrator must set the prices dictionnary.")
        if pair_id not in self.orchestrator_prices:
            return None

        match data_type:
            case DataTypes.SPOT:
                entries = [entry for entry in self.orchestrator_prices[pair_id][data_type].values()]

            case DataTypes.FUTURE:
                entries = []
                for source in self.orchestrator_prices[pair_id][data_type]:
                    if expiry in self.orchestrator_prices[pair_id][data_type][source]:
                        entries.append(self.orchestrator_prices[pair_id][data_type][source][expiry])

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
            self.consecutive_empty_oracle_error += 1
            if self.consecutive_empty_oracle_error >= CONSECUTIVES_EMPTY_ERRORS_LIMIT:
                raise ValueError(
                    "⛔ Oracle entries are still empty after "
                    f"{self.consecutive_empty_oracle_error} tries. "
                    "Publishing does not seem to work?"
                )
            return True

        for data_type, pairs in self.data_config.items():
            for pair in pairs:
                pair_id = str(pair)
                # Poller is incomplete, retrying...
                if pair_id not in self.orchestrator_prices:
                    continue
                # Poller is incomplete, retrying...
                if data_type not in self.orchestrator_prices[pair_id]:
                    continue
                # Warning there - we should have all the prices in the Oracle. We try to fill empty values.
                if data_type not in self.oracle_prices[pair_id]:
                    logger.warn(
                        f"LISTENER {self.id} miss {data_type} prices in oracle entries. Sending notification."
                    )
                    return True

                match data_type:
                    case DataTypes.SPOT:
                        if self._does_oracle_spot_entry_needs_update(
                            pair_id,
                            data_type,
                            self.oracle_prices[pair_id][data_type],
                            self.orchestrator_prices[pair_id][data_type],
                        ):
                            return True

                    case DataTypes.FUTURE:
                        if self._does_oracle_future_entry_needs_update(
                            pair_id,
                            data_type,
                            self.oracle_prices[pair_id][data_type],
                            self.orchestrator_prices[pair_id][data_type],
                        ):
                            return True
        return False

    def _does_oracle_spot_entry_needs_update(
        self,
        pair_id: str,
        data_type: DataTypes,
        oracle_entry: SpotEntry,
        orchestrator_entries: Dict[SourceName, Entry],
    ) -> bool:
        """
        Check if a spot oracle entry needs to be updated.
        """
        # 1. Check if the oracle entry is outdated
        newest_spot_entry = self._get_latest_orchestrator_entry(pair_id, data_type)
        if self._oracle_entry_is_outdated(pair_id, oracle_entry, newest_spot_entry):
            return True

        # 2. Check if the oracle entry is deviating too much from new sources
        orchestrator_median_price = statistics.median(
            [entry.price for entry in list(orchestrator_entries.values())]
        )
        if self._new_price_is_deviating(pair_id, orchestrator_median_price, oracle_entry.price):
            return True

    def _does_oracle_future_entry_needs_update(
        self,
        pair_id: str,
        data_type: DataTypes,
        oracle_entry: Dict[ExpiryTimestamp, FutureEntry],
        orchestrator_entries: Dict[SourceName, FuturePrices],
    ) -> bool:
        """
        Check if a future oracle entry needs to be updated.
        """
        # 1. Check if the oracle entry is outdated
        if self._future_entries_are_outdated(pair_id, data_type, oracle_entry):
            return True

        # 2. Check if the oracle entry is deviating too much from new sources
        for oracle_expiry, o_entry in oracle_entry.items():
            future_prices = []

            for dict_future_entry in orchestrator_entries.values():
                for expiry, future_entry in dict_future_entry.items():
                    if expiry == oracle_expiry:
                        future_prices.append(future_entry.price)

            orchestrator_median_price = statistics.median(future_prices)
            if self._new_price_is_deviating(pair_id, orchestrator_median_price, o_entry.price):
                return True

    def _future_entries_are_outdated(
        self, pair_id: str, data_type: DataTypes, entries: Dict[ExpiryTimestamp, FutureEntry]
    ) -> bool:
        """
        Compare each timestamp future price together & returns True if one of them is
        outdated.
        """
        for expiry, oracle_entry in entries.items():
            orchestrator_entry = self._get_latest_orchestrator_entry(pair_id, data_type, expiry)
            if self._oracle_entry_is_outdated(pair_id, oracle_entry, orchestrator_entry):
                return True
        return False

    def _new_price_is_deviating(self, pair_id: str, new_price: int, oracle_price: int) -> bool:
        """
        Check if a new price is in the bounds allowed by the configuration.
        """
        max_deviation = self.price_config.price_deviation * oracle_price
        deviation = abs(new_price - oracle_price)
        is_deviating = deviation >= max_deviation
        if is_deviating:
            deviation_percentage = (deviation / oracle_price) * 100
            logger.info(
                f"🔔 Newest median price for {pair_id} is deviating from the "
                f"config bounds (deviation = {deviation_percentage:.2f}%, more than "
                f"{self.price_config.price_deviation * 100}%). "
                "Triggering an update!"
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
        oracle_entry_timestamp = oracle_entry.get_timestamp()
        delta_t = newest_entry.get_timestamp() - oracle_entry_timestamp
        is_outdated = delta_t > max_time_elapsed

        if is_outdated:
            logger.info(
                f"🔔 Latest oracle entry for {pair_id} is too old (delta = {delta_t}, "
                f"more than {self.price_config.time_difference}s). "
                "Triggering an update!"
            )

        return is_outdated

    def _notify(self) -> None:
        """
        Sends a notification.
        """
        logger.info(f"🏓 LISTENER: [{self.id}] sending notification to the Orchestrator!")
        self.notification_event.set()

    def _log_listener_spawning(self) -> None:
        """
        Logs that a thread has been successfuly spawned for this listener.
        """
        pairs = self.price_config.get_all_assets()
        logging.info(f"👂 Spawned listener [{self.id}] for pairs: {pairs}")
