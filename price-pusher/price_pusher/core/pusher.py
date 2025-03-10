import asyncio
import time
import logging
from typing import List, Optional, Dict, Set
from starknet_py.contract import InvokeResult
from starknet_py.net.client_errors import ClientError
from requests.exceptions import RequestException

from abc import ABC, abstractmethod

from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.constants import RPC_URLS
from pragma_sdk.onchain.utils import pick_random_rpc

logger = logging.getLogger(__name__)

CONSECUTIVES_PUSH_ERRORS_LIMIT = 10
WAIT_FOR_ACCEPTANCE_MAX_RETRIES = 60
RPC_HEALTH_CHECK_INTERVAL = 60  # Check RPC health every minute
MAX_RPC_FAILURES = 3  # Number of failures before switching RPC


class IPricePusher(ABC):
    client: PragmaClient
    consecutive_push_error: int
    onchain_lock: asyncio.Lock

    @abstractmethod
    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]: ...


class PricePusher(IPricePusher):
    def __init__(self, client: PragmaClient):
        self.client = client
        self.consecutive_push_error = 0
        self.onchain_lock = asyncio.Lock()

        # RPC health monitoring
        self.current_rpc_failures = 0
        self.failed_rpcs: Set[str] = set()
        if isinstance(self.client, PragmaOnChainClient):
            self.network = self.client.network
            asyncio.create_task(self._monitor_rpc_health())

    @property
    def is_publishing_on_chain(self) -> bool:
        return isinstance(self.client, PragmaOnChainClient)

    async def _check_rpc_health(self, rpc_url: str) -> bool:
        """Check if an RPC endpoint is healthy by making a simple request."""
        try:
            # Use the client's existing connection to make a simple call
            await self.client.full_node_client.get_block_number()
            return True
        except (ClientError, RequestException) as e:
            logger.warning(f"RPC health check failed for {rpc_url}: {str(e)}")
            return False

    async def _switch_rpc(self) -> bool:
        """Switch to a different RPC URL if the current one is failing."""
        if not isinstance(self.client, PragmaOnChainClient):
            return False

        available_rpcs = [
            url for url in RPC_URLS[self.network] if url not in self.failed_rpcs
        ]
        if not available_rpcs:
            # If all RPCs have failed, clear the failed list and try again
            self.failed_rpcs.clear()
            available_rpcs = RPC_URLS[self.network]

        try:
            new_rpc = pick_random_rpc(self.network, available_rpcs)
            logger.info(f"Switching to new RPC: {new_rpc}")
            self.client.full_node_client = self.client.client = (
                self.client._create_full_node_client(new_rpc)
            )
            return True
        except ValueError as e:
            logger.error(f"Failed to switch RPC: {str(e)}")
            return False

    async def _monitor_rpc_health(self):
        """Continuously monitor RPC health and switch if needed."""
        if not isinstance(self.client, PragmaOnChainClient):
            return

        while True:
            try:
                current_rpc = self.client.full_node_client.url
                is_healthy = await self._check_rpc_health(current_rpc)

                if not is_healthy:
                    self.current_rpc_failures += 1
                    if self.current_rpc_failures >= MAX_RPC_FAILURES:
                        logger.warning(
                            f"RPC {current_rpc} has failed {MAX_RPC_FAILURES} times, switching..."
                        )
                        self.failed_rpcs.add(current_rpc)
                        if await self._switch_rpc():
                            self.current_rpc_failures = 0
                else:
                    self.current_rpc_failures = 0

            except Exception as e:
                logger.error(f"Error in RPC health monitoring: {str(e)}")

            await asyncio.sleep(RPC_HEALTH_CHECK_INTERVAL)

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
            if isinstance(self.client, PragmaOnChainClient):
                async with self.onchain_lock:
                    start_t = time.time()
                    response = await self.client.publish_many(entries)
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
            self.consecutive_push_error += 1
            logger.error(f"⛔ PUSHER: could not publish entrie(s): {e}")

            if isinstance(self.client, PragmaOnChainClient):
                # If we have RPC issues, try switching to a different RPC
                if "RPC" in str(e) or isinstance(e, (ClientError, RequestException)):
                    self.current_rpc_failures += 1
                    if self.current_rpc_failures >= MAX_RPC_FAILURES:
                        logger.warning(
                            "RPC issues detected, attempting to switch RPC..."
                        )
                        self.failed_rpcs.add(self.client.full_node_client.url)
                        if await self._switch_rpc():
                            self.current_rpc_failures = 0
                            # Retry the publish operation with new RPC
                            return await self.update_price_feeds(entries)

            if self.consecutive_push_error >= CONSECUTIVES_PUSH_ERRORS_LIMIT:
                raise ValueError(
                    f"⛔ PUSHER: Failed to publish entries {self.consecutive_push_error} "
                    "times in a row. Something is wrong!"
                )

            return None


async def wait_for_txs_acceptance(invocations: List[InvokeResult]) -> None:
    """
    Wait for all the transactions in the passed list to be accepted on-chain.
    Raises an error if one transaction is not accepted.
    """
    for invocation in invocations:
        nonce = invocation.invoke_transaction.nonce
        logger.info(
            f"  ⏳ waiting for TX {hex(invocation.hash)} (nonce={nonce}) to be accepted..."
        )
        await invocation.wait_for_acceptance(check_interval=1)
