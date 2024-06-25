import asyncio
import logging

from abc import ABC, abstractmethod
from typing import Optional, List

from pragma.core.entry import Entry, SpotEntry
from pragma.core.assets import PragmaAsset, AssetType

from price_pusher.core.request_handlers.interface import IRequestHandler
from price_pusher.type_aliases import (
    DurationInSeconds,
    LatestOrchestratorPairPrices,
    LatestOraclePairPrices,
)

logger = logging.getLogger(__name__)


class IPriceListener(ABC):
    """
    Sends a signal to the Orchestrator when we need to update prices.
    """

    request_handler: IRequestHandler
    oracle_prices: LatestOraclePairPrices
    orchestrator_prices: Optional[LatestOrchestratorPairPrices]
    assets: List[PragmaAsset]
    notification_event: asyncio.Event
    polling_frequency_in_s: DurationInSeconds

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
        polling_frequency_in_s: DurationInSeconds,
        assets: List[PragmaAsset],
    ) -> None:
        self.request_handler = request_handler

        self.oracle_prices = {}
        self.orchestrator_prices = None

        self.polling_frequency_in_s = polling_frequency_in_s
        self.assets = assets

        self.notification_event = asyncio.Event()

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
            for asset in self.assets
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for entry in results:
            if isinstance(entry, Exception):
                logger.error(f"Error fetching oracle price: {entry}")
                continue
            if entry is None:
                continue
            pair_id = entry.get_pair_id()
            asset_type = "SPOT" if isinstance(entry, SpotEntry) else "FUTURE"
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
        return max(entries, key=lambda entry: entry.listener.timestamp, default=None)

    async def _does_oracle_needs_update(self) -> bool:
        # TODO
        return False

    def _notify(self) -> None:
        """
        Sends a notification.
        """
        logger.info("🏓 Sending notification to the Orchestrator!")
        self.notification_event.set()
