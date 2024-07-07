from abc import ABC, abstractmethod

from typing import List, Optional, Dict

from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry

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
        logger.info(f"🏋️ PUSHER: 👷‍♂️ processing {len(entries)} new assets to push...")
        try:
            response = await self.client.publish_entries(entries)  # TODO: add execution config
            logger.info(f"🏋️ PUSHER: ✅ Successfully published {len(entries)} entries!")
            logger.debug(f"Response from the API: {response}")

            return response
        except Exception as e:
            logger.error(f"🏋️ PUSHER: ⛔ could not publish entries : {e}")
            return None
