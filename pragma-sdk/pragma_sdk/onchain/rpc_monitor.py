import asyncio
from starknet_py.net.client_errors import ClientError
from requests.exceptions import RequestException

from pragma_sdk.common.logging import get_pragma_sdk_logger
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.constants import RPC_URLS
from pragma_sdk.onchain.utils import pick_random_rpc

logger = get_pragma_sdk_logger()

RPC_HEALTH_CHECK_INTERVAL = 60  # Check RPC health every minute
MAX_RPC_FAILURES = 3  # Number of failures before switching RPC


class RPCHealthMonitor:
    """
    A class to monitor RPC health and automatically switch to healthy RPCs when needed.
    This helps maintain service uptime by avoiding failed RPCs and automatically
    switching to working alternatives.

    Usage:
        client = PragmaOnChainClient(...)
        rpc_monitor = RPCHealthMonitor(client)
        asyncio.create_task(rpc_monitor.monitor_rpc_health())

        # When handling RPC errors:
        try:
            await client.some_operation()
        except (ClientError, RequestException) as e:
            rpc_monitor.record_failure()
            if await rpc_monitor.should_switch_rpc():
                await rpc_monitor.switch_rpc()
                # Retry operation...
    """

    def __init__(self, client: PragmaOnChainClient):
        """
        Initialize the RPC health monitor.

        Args:
            client: The PragmaOnChainClient instance to monitor
        """
        self.client = client
        self.current_rpc_failures = 0
        self.failed_rpcs: set[str] = set()
        self.network = client.network

    def record_failure(self) -> None:
        """Record an RPC failure."""
        self.current_rpc_failures += 1

    async def should_switch_rpc(self) -> bool:
        """Check if we should switch to a different RPC based on failure count."""
        return self.current_rpc_failures >= MAX_RPC_FAILURES

    async def check_rpc_health(self) -> bool:
        """
        Check if an RPC endpoint is healthy by making a simple request.

        Returns:
            bool: True if the RPC is healthy, False otherwise
        """
        try:
            await self.client.full_node_client.get_block_number()
            return True
        except (ClientError, RequestException) as e:
            current_rpc = self.client.full_node_client.url
            logger.warning(f"RPC health check failed for {current_rpc}: {str(e)}")
            return False

    async def switch_rpc(self) -> bool:
        """
        Switch to a different RPC URL if the current one is failing.

        Returns:
            bool: True if successfully switched to a new RPC, False otherwise
        """
        current_rpc = self.client.full_node_client.url
        self.failed_rpcs.add(current_rpc)

        available_rpcs = [
            url for url in RPC_URLS[self.network] if url not in self.failed_rpcs
        ]
        if not available_rpcs:
            # If all RPCs have failed, clear all except current one and try again
            self.failed_rpcs = {current_rpc}  # Keep current RPC in failed list
            available_rpcs = [
                url for url in RPC_URLS[self.network] if url not in self.failed_rpcs
            ]

        try:
            new_rpc = pick_random_rpc(self.network, available_rpcs)
            logger.info(f"Switching to new RPC: {new_rpc}")
            new_client = self.client._create_full_node_client(new_rpc)
            self.client.full_node_client = self.client.client = new_client
            self.current_rpc_failures = 0
            return True
        except ValueError as e:
            logger.error(f"Failed to switch RPC: {str(e)}")
            return False

    async def monitor_rpc_health(self):
        """
        Continuously monitor RPC health and switch if needed.
        This should be run as a background task.
        """
        while True:
            try:
                current_rpc = self.client.full_node_client.url
                is_healthy = await self.check_rpc_health()

                if not is_healthy:
                    self.current_rpc_failures += 1
                    if await self.should_switch_rpc():
                        logger.warning(
                            f"RPC {current_rpc} has failed {MAX_RPC_FAILURES} times, switching..."
                        )
                        await self.switch_rpc()
                else:
                    self.current_rpc_failures = 0

            except Exception as e:
                logger.error(f"Error in RPC health monitoring: {str(e)}")

            await asyncio.sleep(RPC_HEALTH_CHECK_INTERVAL)
