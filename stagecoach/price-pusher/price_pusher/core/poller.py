from abc import ABC, abstractmethod

from typing import List, Dict

from pragma.publisher.client import FetcherClient

import logging

logger = logging.getLogger(__name__)


class IPricePoller(ABC):
    @abstractmethod
    async def poll_prices(self, pair_ids: List[str]) -> None:
        pass


class PricePoller(IPricePoller, ABC):
    def __init__(self, client: FetcherClient) -> Dict:
        pass

    def poll_prices(self) -> Dict:
        pass
