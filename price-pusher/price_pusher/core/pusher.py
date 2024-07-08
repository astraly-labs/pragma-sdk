from abc import ABC, abstractmethod

from typing import List, Optional, Dict

from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry

import logging

logger = logging.getLogger(__name__)

CONSECUTIVES_PUSH_ERRORS_LIMIT = 10


class IPricePusher(ABC):
    client: PragmaClient
    consecutive_push_error: int

    @abstractmethod
    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]: ...


class PricePusher(IPricePusher):
    def __init__(self, client: PragmaClient) -> None:
        self.client = client
        self.consecutive_push_error = 0

    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]:
        """
        Push the entries passed as parameter with the internal pragma client.
        """
        logger.info(f"🏋️ PUSHER: 👷‍♂️ processing {len(entries)} new asset(s) to push...")
        try:
            response = await self.client.publish_entries(entries)  # TODO: add execution config
            logger.info(f"🏋️ PUSHER: ✅ Successfully published {len(entries)} entrie(s)!")
            logger.debug(f"Response from the API: {response}")

            return response
        except Exception as e:
            logger.error(f"🏋️ PUSHER: ⛔ could not publish entrie(s): {e}")
            self.consecutive_push_error += 1
            if self.consecutive_push_error >= CONSECUTIVES_PUSH_ERRORS_LIMIT:
                raise ValueError(
                    "⛔ Pusher tried to push for "
                    f"{self.consecutive_push_error} times and still failed. "
                    "Pusher does not seems to work? Stopping here."
                )
            return None
