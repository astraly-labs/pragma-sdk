from abc import ABC, abstractmethod

from typing import List, Optional, Dict

from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry

from pragma_sdk.onchain.client import PragmaOnChainClient

import logging

logger = logging.getLogger(__name__)

CONSECUTIVES_PUSH_ERRORS_LIMIT = 10
WAIT_FOR_ACCEPTANCE_MAX_RETRIES = 60


class IPricePusher(ABC):
    client: PragmaClient
    consecutive_push_error: int

    @abstractmethod
    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]: ...


class PricePusher(IPricePusher):
    def __init__(self, client: PragmaClient) -> None:
        self.client = client
        self.consecutive_push_error = 0

    @property
    def is_publishing_on_chain(self) -> bool:
        return isinstance(self.client, PragmaOnChainClient)

    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]:
        """
        Push the entries passed as parameter with the internal pragma client.
        """
        logger.info(f"🏋️ PUSHER: 👷‍♂️ processing {len(entries)} new asset(s) to push...")
        try:
            response = await self.client.publish_entries(entries)
            if self.is_publishing_on_chain:
                last_invocation = response[-1]
                logger.info(
                    f"🏋️ PUSHER: ⏳ waiting TX hash {hex(last_invocation.hash)} to be executed..."
                )
                await last_invocation.wait_for_acceptance(
                    check_interval=1, retries=WAIT_FOR_ACCEPTANCE_MAX_RETRIES
                )
            logger.info(f"🏋️ PUSHER: ✅ Successfully published {len(entries)} entrie(s)!")
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
