from abc import ABC, abstractmethod
from typing import Optional, List

from pragma.core.entry import Entry
from pragma.core.assets import PragmaAsset
from pragma.publisher.client import PragmaPublisherClientT

from price_pusher.type import DurationInSeconds
from pragma.core.assets import AssetType


class IPriceListener(ABC):
    """
    Sends a signal to the Orchestrator when we need to update prices.

    TODO: What is the trigger condition for push?
    """

    client: PragmaPublisherClientT
    ref_latest_price: dict
    polling_frequency: DurationInSeconds
    assets: List[PragmaAsset]

    @abstractmethod
    def set_ref_latest_price(self, ref_latest_price: dict) -> None: ...

    @abstractmethod
    async def run(self) -> None: ...

    @abstractmethod
    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]: ...

    @abstractmethod
    def get_latest_registered_entry(
        self, pair_id: str, asset_type: AssetType
    ) -> Optional[Entry]: ...


class PriceListener(IPriceListener):
    async def run(self) -> None:
        raise NotImplementedError("Must be implemented by childrens.")

    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        raise NotImplementedError("Must be implemented by childrens.")

    def __init__(
        self,
        client: PragmaPublisherClientT,
        polling_frequency: DurationInSeconds,
        assets: List[PragmaAsset],
    ) -> None:
        self.client = client
        self.polling_frequency = polling_frequency
        self.assets = assets
        self.ref_latest_price: Optional[dict] = None

    def set_ref_latest_price(self, ref_latest_price: dict) -> None:
        """
        Set the reference of the orchestrator prices in the Listener.
        """
        self.ref_latest_price = ref_latest_price

    def get_latest_registered_entry(
        self, pair_id: str, asset_type: AssetType
    ) -> Optional[Entry]:
        """
        Retrieves the latest registered entry from the latest prices.
        """
        if self.ref_latest_price is None:
            raise ValueError("Orchestrator must pass the prices dictionnary.")
        entries = [
            entry for entry in self.ref_latest_price[pair_id][asset_type].values()
        ]
        most_recent_entry = None
        for entry in entries:
            if most_recent_entry is None:
                most_recent_entry = entry
                continue
            if most_recent_entry.entry.timestamp > entry.timestamp:
                most_recent_entry = entry
        return most_recent_entry
