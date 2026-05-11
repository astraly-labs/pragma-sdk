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

from pragma_sdk.miden.client import PragmaMidenClient, MidenEntry

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
        miden_client: Optional[PragmaMidenClient] = None,
    ):
        self.client = client
        self.consecutive_push_error = 0
        self.onchain_lock = asyncio.Lock()
        self.on_successful_push = on_successful_push
        self.miden_client = miden_client
        # At most one Miden publish in flight at a time. New ticks skip rather
        # than queue when one is already running — that way a hung Miden
        # publish_batch never accumulates zombie threads behind it.
        self._miden_sem: Optional[asyncio.Semaphore] = (
            asyncio.Semaphore(1) if miden_client is not None else None
        )
        # asyncio.create_task() returns a Task that the event loop only keeps
        # a weak reference to. If our caller doesn't hold a strong ref, the
        # GC can collect the task mid-execution and cancel it silently.
        # Cf. https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
        self._miden_tasks: set[asyncio.Task] = set()

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
            await asyncio.sleep(5)
            self.consecutive_push_error = 0

            # Notify health server of successful push
            if self.on_successful_push:
                self.on_successful_push()

            # Miden publishing — fire-and-forget, isolated from Starknet.
            # Hold a strong reference in self._miden_tasks until done, so
            # the task isn't garbage-collected mid-publish.
            if self.miden_client is not None:
                task = asyncio.create_task(self._publish_to_miden(entries))
                self._miden_tasks.add(task)
                task.add_done_callback(self._miden_tasks.discard)
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

    async def _publish_to_miden(self, entries: List[Entry]) -> None:
        """
        Publish entries to Miden in the background.
        Completely isolated — any failure here has zero impact on the Starknet loop.
        Skipped when a previous batch is still in flight.
        """
        if self._miden_sem is None or self._miden_sem.locked():
            if self._miden_sem is not None:
                logger.warning(
                    "🌐 MIDEN: previous batch still in flight, skipping this tick"
                )
            return
        # Pragma publishes one Starknet entry per (pair, source), so a tick
        # batch can contain e.g. BTC/USD × 5 sources, ETH/USD × 5 sources, ...
        # Miden has no notion of "source": publish_entry overwrites the
        # storage map at faucet_id, so duplicate calls within the same tx
        # are wasted work, and the Miden prover cost grows linearly with
        # script length. 22 raw entries (5 pairs × ~4 sources) was taking
        # >60s and >4Gi RSS to prove. Aggregate one MidenEntry per pair
        # using the median price (matches Pragma's on-chain aggregation).
        from statistics import median
        per_pair: dict[str, list[MidenEntry]] = {}
        for e in entries:
            me = MidenEntry.from_starknet_entry(e)
            if me is not None:
                per_pair.setdefault(me.pair, []).append(me)
        miden_entries = [
            MidenEntry(
                pair=pair,
                price=int(median(m.price for m in mes)),
                decimals=mes[0].decimals,
                timestamp=max(m.timestamp for m in mes),
            )
            for pair, mes in per_pair.items()
        ]
        if not miden_entries:
            return
        async with self._miden_sem:
            try:
                results = await self.miden_client.publish_entries(miden_entries)
                ok = sum(results)
                logger.info(f"🌐 MIDEN: published {ok}/{len(miden_entries)} entries")
            except Exception as e:
                logger.error(f"🌐 MIDEN: publish failed (Starknet unaffected): {e}")
