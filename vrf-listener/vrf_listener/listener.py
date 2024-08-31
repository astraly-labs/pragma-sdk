import asyncio
import logging
import traceback

from typing import Optional, List, Set


from pragma_sdk.onchain.types import RandomnessRequest
from pragma_sdk.onchain.client import PragmaOnChainClient

from vrf_listener.indexer import Indexer
from vrf_listener.safe_queue import ThreadSafeQueue

logger = logging.getLogger(__name__)


class Listener:
    pragma_client: PragmaOnChainClient
    private_key: int
    requests_queue: ThreadSafeQueue
    check_requests_interval: int
    processed_requests: Set[RandomnessRequest]
    requests_to_retry: Set[RandomnessRequest]
    indexer: Optional[Indexer] = None

    def __init__(
        self,
        pragma_client: PragmaOnChainClient,
        private_key: int | str,
        requests_queue: ThreadSafeQueue,
        check_requests_interval: int,
        ignore_request_threshold: int,
        indexer: Optional[Indexer] = None,
    ) -> None:
        self.pragma_client = pragma_client
        if isinstance(private_key, str):
            private_key = int(private_key, 16)
        self.private_key = private_key
        self.requests_queue = requests_queue
        self.check_requests_interval = check_requests_interval
        self.ignore_request_threshold = ignore_request_threshold
        self.processed_requests = set()
        self.requests_to_retry = set()
        self.indexer = indexer

    @property
    def is_indexing(self) -> bool:
        return self.indexer is not None

    async def run_forever(self) -> None:
        """
        Handle VRF requests forever.
        """
        logger.info("👂 Listening for VRF requests!")
        while True:
            if self.is_indexing:
                events = await self._consume_requests_queue()
                if len(events) > 0:
                    logger.info(f"🔥 Consumed {len(events)} event(s) from the indexing queue...")
                if len(self.requests_to_retry) > 0:
                    logger.info(
                        f"🧑‍⚕ Found {len(self.requests_to_retry)} event(s) that failed before, "
                        "adding to the requests list..."
                    )
                    events += list(set(list(self.requests_to_retry)))
                    self.requests_to_retry = set()
            try:
                await self.pragma_client.handle_random(
                    private_key=self.private_key,
                    ignore_request_threshold=self.ignore_request_threshold,
                    pre_indexed_requests=events if self.indexer is not None else None,
                )
            except Exception as e:
                logger.error(f"⛔ Error while handling randomness request: {e}")
                logger.error(f"Traceback:\n{''.join(traceback.format_exc())}")
                # If the submission failed, keep track of the failed requests & retry next loop
                if self.is_indexing:
                    logger.info("🏥 Saving failed requests for next loop...")
                    self.requests_to_retry.update(events)
            await asyncio.sleep(self.check_requests_interval)

    async def _consume_requests_queue(self) -> List[RandomnessRequest]:
        """
        Consumes the whole requests_queue and return the requests.
        """
        events = list()
        while not self.requests_queue.empty():
            try:
                request: RandomnessRequest = await self.requests_queue.get()
                if request not in self.processed_requests:
                    events.append(request)
                    self.processed_requests.add(request)
            except asyncio.QueueEmpty:
                break
        return events
