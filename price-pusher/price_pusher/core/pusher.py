import asyncio
import time
import logging
from typing import List, Optional, Dict, Callable
from starknet_py.contract import InvokeResult

from abc import ABC, abstractmethod

from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.rpc_monitor import RPCHealthMonitor

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
    def __init__(
        self,
        client: PragmaClient,
        on_successful_push: Optional[Callable[[], None]] = None,
    ):
        self.client = client
        self.consecutive_push_error = 0
        self.onchain_lock = asyncio.Lock()
        self.on_successful_push = on_successful_push

        # Setup RPC health monitoring if using onchain client
        if isinstance(self.client, PragmaOnChainClient):
            self.rpc_monitor = RPCHealthMonitor(self.client)
            asyncio.create_task(self.rpc_monitor.monitor_rpc_health())

    @property
    def is_publishing_on_chain(self) -> bool:
        publish_many = getattr(self.client, "publish_many", None)
        return callable(publish_many)

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
        if len(entries) == 0:
            return None

        logger.info(f"📨 PUSHER: processing {len(entries)} new asset(s) to push...")

        try:
            if not callable(getattr(self.client, "publish_many", None)):
                raise TypeError(
                    "PricePusher now requires a client exposing an async publish_many method"
                )

            async with self.onchain_lock:
                start_t = time.time()
                response = await self.client.publish_many(entries)
                await self.wait_for_publishing_acceptance(response)

            end_t = time.time()
            logger.info(
                f"🏋️ PUSHER: ✅ Successfully published {len(entries)} entrie(s)! "
                f"(took {(end_t - start_t):.2f}s)"
            )
            self.consecutive_push_error = 0

            # Notify health server of successful push
            if self.on_successful_push:
                self.on_successful_push()

            return response

        except Exception as e:
            self.consecutive_push_error += 1
            logger.error(f"⛔ PUSHER: could not publish entrie(s): {e}")

            if isinstance(self.client, PragmaOnChainClient):
                # If we have RPC issues, try switching to a different RPC
                self.rpc_monitor.record_failure()
                if await self.rpc_monitor.should_switch_rpc():
                    if await self.rpc_monitor.switch_rpc():
                        # Retry the publish operation with new RPC
                        return await self.update_price_feeds(entries)

            if self.consecutive_push_error >= CONSECUTIVES_PUSH_ERRORS_LIMIT:
                raise ValueError(
                    f"⛔ PUSHER: Failed to publish entries {self.consecutive_push_error} "
                    "times in a row. Something is wrong!"
                )

            return None
