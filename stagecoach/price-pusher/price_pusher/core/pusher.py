from abc import ABC, abstractmethod

from typing import List, Optional, Dict

from price_pusher.type import UnixTimestamp
from pragma.publisher.client import PragmaAPIError, PragmaClient
from pragma.core.entry import Entry

import logging

logger = logging.getLogger(__name__)


class IPricePusher(ABC):
    @abstractmethod
    async def update_price_feed(
        self, pair_ids: List[str], pub_times_to_push: List[UnixTimestamp]
    ) -> None:
        pass


class PricePusher(IPricePusher):
    def __init__(self, client: PragmaClient) -> None:
        self.client = client

    async def update_price_feed(self, entries: List[Entry]) -> Optional[Dict]:
        """
        Push the entries passed as parameter with the internal pragma client.
        """
        try:
            response = self.client.publish_entries(entries)
            logger.debug(f"entries sucessfully published : {response}")
            return response
        except PragmaAPIError as e:
            logger.error(f"failed to update price feed : {e}")
            return None
