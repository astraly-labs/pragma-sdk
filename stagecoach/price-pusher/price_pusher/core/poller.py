from abc import ABC, abstractmethod

from typing import Coroutine, List, Union, Optional, Dict

from price_pusher.type import UnixTimestamp
from pragma.publisher.client import FetcherClient
from pragma.core.entry import Entry

import logging

logger = logging.getLogger(__name__)


class IPricePoller(ABC):
    @abstractmethod
    async def poll_prices(self, pair_ids: List[str]) -> None:
        pass


class PricePoller(IPricePoller, ABC):
    def poll_prices(self, client: FetcherClient) -> Dict:
        pass
