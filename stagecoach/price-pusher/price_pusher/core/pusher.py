from abc import ABC, abstractmethod

from typing import List, Optional, Dict

from pragma.publisher.client import PragmaAPIError, PragmaClient
from pragma.core.entry import Entry

import logging

logger = logging.getLogger(__name__)


class IPricePusher(ABC):
    @abstractmethod
    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]: ...


class PricePusher(IPricePusher):
    def __init__(self, client: PragmaClient) -> None:
        self.client = client

    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]:
        """
        Push the entries passed as parameter with the internal pragma client.
        """
        try:
            response = await self.client.publish_entries(entries)
            logger.info(f"entries sucessfully published : {response}")
            return response
        except PragmaAPIError as e:
            logger.error(f"failed to update price feed : {e}")
            return None
