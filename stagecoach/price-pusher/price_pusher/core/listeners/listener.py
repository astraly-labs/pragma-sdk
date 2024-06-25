import asyncio
import logging

from abc import ABC, abstractmethod
from typing import Optional, List

from pragma.core.entry import Entry
from pragma.core.assets import PragmaAsset
from pragma.publisher.client import PragmaPublisherClientT
from pragma.core.assets import AssetType

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

    client: PragmaPublisherClientT
    oracle_prices: LatestOraclePairPrices
    orchestrator_prices: Optional[LatestOrchestratorPairPrices]
    assets: List[PragmaAsset]
    notification_event: asyncio.Event
    polling_frequency_in_s: DurationInSeconds

    @abstractmethod
    async def _fetch_latest_oracle_pair_price(
        self, asset: PragmaAsset
    ) -> Optional[Entry]: ...

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
        client: PragmaPublisherClientT,
        polling_frequency_in_s: DurationInSeconds,
        assets: List[PragmaAsset],
    ) -> None:
        self.client = client
        self.oracle_prices = {}
        self.orchestrator_prices = None
        self.assets = assets
        self.notification_event = asyncio.Event()
        self.polling_frequency_in_s = polling_frequency_in_s

    async def _fetch_latest_oracle_pair_price(
        self, asset: PragmaAsset
    ) -> Optional[Entry]:
        raise NotImplementedError("Must be implemented by children listener.")

    async def _fetch_all_oracle_prices(self) -> None:
        """
        Fetch the latest oracle prices for all assets in parallel.
        """
        tasks = [self._fetch_latest_oracle_pair_price(asset) for asset in self.assets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error fetching oracle price: {result}")
                continue
            if result is None:
                continue
            pair_id = result.get_pair_id()
            self.oracle_prices[pair_id] = result

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
        # TODO: should be implemented here (the same for every listeners)
        return False

    def _notify(self) -> None:
        """
        Sends a notification.
        """
        logger.info("🏓 Sending notification to the Orchestrator!")
        self.notification_event.set()

    def set_orchestrator_prices(self, orchestrator_prices: dict) -> None:
        """
        Set the reference of the orchestrator prices in the Listener.
        """
        self.orchestrator_prices = orchestrator_prices

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
