import asyncio
import logging

from abc import ABC, abstractmethod
from typing import Optional, List

from pragma.core.entry import Entry
from pragma.core.assets import PragmaAsset
from pragma.publisher.client import PragmaPublisherClientT
from pragma.core.assets import AssetType

from price_pusher.type_aliases import DurationInSeconds, LatestPairPrices

logger = logging.getLogger(__name__)


class IPriceListener(ABC):
    """
    Sends a signal to the Orchestrator when we need to update prices.
    """

    client: PragmaPublisherClientT
    oracle_prices: LatestPairPrices
    orchestrator_prices: Optional[LatestPairPrices]
    assets: List[PragmaAsset]
    notification_event: asyncio.Event
    polling_frequency_in_s: DurationInSeconds

    @abstractmethod
    def set_orchestrator_prices(
        self, orchestrator_prices: LatestPairPrices
    ) -> None: ...

    @abstractmethod
    def get_latest_registered_entry(
        self, pair_id: str, asset_type: AssetType
    ) -> Optional[Entry]: ...

    @abstractmethod
    async def get_latest_price_info(self, pair_id: str) -> Optional[Entry]: ...

    @abstractmethod
    def notify(self) -> None: ...

    @abstractmethod
    async def run_forever(self) -> None: ...


class PriceListener(IPriceListener):
    async def run_forever(self) -> None:
        raise NotImplementedError("Must be implemented by children listener.")

    async def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        raise NotImplementedError("Must be implemented by children listener.")

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

    def set_orchestrator_prices(self, orchestrator_prices: dict) -> None:
        """
        Set the reference of the orchestrator prices in the Listener.
        """
        self.orchestrator_prices = orchestrator_prices

    def get_latest_registered_entry(
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

    def notify(self) -> None:
        """
        Sends a notification.
        """
        logger.info("🏓 Sending notification to the Orchestrator!")
        self.notification_event.set()
