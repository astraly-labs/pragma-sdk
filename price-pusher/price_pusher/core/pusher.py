import asyncio
import time

from abc import ABC, abstractmethod

from typing import List, Optional, Dict
from starknet_py.contract import InvokeResult

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
    onchain_lock: asyncio.Lock

    @abstractmethod
    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]: ...


class PricePusher(IPricePusher):
    def __init__(self, client: PragmaClient) -> None:
        self.client = client
        self.consecutive_push_error = 0
        self.onchain_lock = asyncio.Lock()

    @property
    def is_publishing_on_chain(self) -> bool:
        return isinstance(self.client, PragmaOnChainClient)

    async def wait_for_publishing_acceptance(self, invocations: List[InvokeResult]):
        """
        Waits for all publishing TX to be accepted on-chain.
        """
        for invocation in invocations:
            nonce = invocation.invoke_transaction.nonce
            logger.info(
                f"🏋️ PUSHER: ⏳ Waiting for TX {hex(invocation.hash)} (nonce={nonce}) to be accepted..."
            )
            await invocation.wait_for_acceptance(check_interval=1)

    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]:
        """
        Push the entries passed as parameter with the internal pragma client.
        """
        try:
            logger.info(
                f"🏋️ PUSHER: 👷‍♂️ processing {len(entries)} new asset(s) to push..."
            )

            if self.is_publishing_on_chain:
                async with self.onchain_lock:
                    start_t = time.time()
                    response = await self.client.publish_entries(entries)
                    await self.wait_for_publishing_acceptance(response)
            else:
                start_t = time.time()
                response = await self.client.publish_entries(
                    entries, publish_to_websocket=True
                )

            end_t = time.time()
            logger.info(
                f"🏋️ PUSHER: ✅ Successfully published {len(entries)} entrie(s)! "
                f"(took {(end_t - start_t):.2f}s)"
            )
            self.consecutive_push_error = 0
            return response

        except Exception as e:
            logger.error(f"🏋️ PUSHER: ⛔ could not publish entrie(s): {e}")
            self.consecutive_push_error += 1

        if self.consecutive_push_error >= CONSECUTIVES_PUSH_ERRORS_LIMIT:
            raise ValueError(
                f"⛔ Pusher failed {self.consecutive_push_error} times in a row. Stopping."
            )
        return None
