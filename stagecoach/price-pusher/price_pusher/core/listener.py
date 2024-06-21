import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from pragma.core.assets import (
    PragmaAsset,
)
from pragma.core.entry import Entry

from price_pusher.types import DurationInSeconds


class IPriceListener(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        pass


class ChainPriceListener(IPriceListener, ABC):
    def __init__(
        self, polling_frequency: DurationInSeconds, price_items: List[PragmaAsset]
    ) -> None:
        self.polling_frequency = polling_frequency
        self.price_items = price_items
        self.latest_price_info: Dict[str, Entry] = {}

    async def start(self) -> None:
        await self.poll_prices()
        while True:
            await asyncio.sleep(self.polling_frequency)
            await self.poll_prices()

    async def poll_prices(self) -> None:
        for item in self.price_items:
            current_price_info = await self.get_on_chain_price_info(item.id)
            if current_price_info:
                self.update_latest_price_info(item.id, current_price_info)

    def update_latest_price_info(self, pair_id: str, observed_price: Entry) -> None:
        cached_latest_price_info: Optional[Entry] = self.get_latest_price_info(pair_id)

        if (
            cached_latest_price_info
            and cached_latest_price_info.get_timestamp()
            > observed_price.get_timestamp()
        ):
            return

        self.latest_price_info[pair_id] = observed_price

    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]:
        return self.latest_price_info.get(pair_id)

    @abstractmethod
    async def get_on_chain_price_info(self, pair_id: str) -> Optional[Entry]:
        pass
