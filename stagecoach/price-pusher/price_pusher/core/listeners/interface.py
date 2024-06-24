from abc import ABC, abstractmethod
from typing import Optional

from pragma.core.entry import Entry


class IPriceListener(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    def get_latest_price_info(self, pair_id: str) -> Optional[Entry]: ...
