from abc import ABC, abstractmethod

from typing import List

from price_pusher.types import UnixTimestamp


class IPricePusher(ABC):
    @abstractmethod
    async def update_price_feed(
        self, pair_ids: List[str], pub_times_to_push: List[UnixTimestamp]
    ) -> None:
        pass
