import asyncio
import time
import logging
from typing import List, Optional, Dict, Callable
from starknet_py.contract import InvokeResult

from abc import ABC, abstractmethod

from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.types.entry import Entry
from pragma_sdk.common.utils import felt_to_str
from pragma_sdk.common.fetchers.metrics import metrics

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.rpc_monitor import RPCHealthMonitor

from pragma_sdk.miden.client import PragmaMidenClient, MidenEntry

logger = logging.getLogger(__name__)

CONSECUTIVES_PUSH_ERRORS_LIMIT = 10
WAIT_FOR_ACCEPTANCE_MAX_RETRIES = 60
# The PublisherRegistry whitelists sources per publisher and the oracle rejects
# a whole publish_data_entries batch on the first entry whose source is not
# whitelisted ('Not allowed for source'). The pusher reads the whitelist and
# drops such entries itself, so a new fetcher degrades to a warning instead of
# taking every Starknet push down (LIDO on 2026-06-13, KRAKEN in #322).
ALLOWED_SOURCES_TTL_S = 600


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
        publisher_name: Optional[str] = None,
    ):
        self.client = client
        self.consecutive_push_error = 0
        self.onchain_lock = asyncio.Lock()
        self.on_successful_push = on_successful_push
        self.miden_client = miden_client
        self.publisher_name = publisher_name
        # sources whitelisted on-chain for this publisher, None until read once
        self._allowed_sources: Optional[set[int]] = None
        self._allowed_sources_at: float = 0.0

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

    async def refresh_allowed_sources(self) -> None:
        """
        Read the publisher's whitelisted sources from the PublisherRegistry,
        at most every ALLOWED_SOURCES_TTL_S. A read failure keeps the last
        known whitelist; if none was ever read, entries are not filtered.
        """
        get_sources = getattr(self.client, "get_publisher_sources", None)
        if self.publisher_name is None or not callable(get_sources):
            return
        if time.time() - self._allowed_sources_at < ALLOWED_SOURCES_TTL_S:
            return
        try:
            sources = await get_sources(self.publisher_name)
            self._allowed_sources = {int(source) for source in sources}
            self._allowed_sources_at = time.time()
            logger.info(
                f"🧾 PUSHER: {len(self._allowed_sources)} source(s) whitelisted "
                f"on-chain for {self.publisher_name}"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ PUSHER: could not read the whitelisted sources of "
                f"{self.publisher_name} ({e}); "
                + (
                    "keeping the previous whitelist"
                    if self._allowed_sources is not None
                    else "entries will not be filtered"
                )
            )

    def filter_allowed_sources(self, entries: List[Entry]) -> List[Entry]:
        """
        Drop the entries whose source is not whitelisted on-chain for this
        publisher. They would make the oracle reject their whole batch.
        """
        if self._allowed_sources is None:
            return entries
        kept: List[Entry] = []
        for entry in entries:
            source = getattr(getattr(entry, "base", None), "source", None)
            if source is None or int(source) in self._allowed_sources:
                kept.append(entry)
                continue
            pair = felt_to_str(getattr(entry, "pair_id", 0))
            source_name = felt_to_str(source)
            logger.warning(
                f"⚠️ PUSHER: dropping {pair} from {source_name}: source not "
                f"whitelisted for {self.publisher_name} in the PublisherRegistry"
            )
            metrics().rejected(pair, source_name, "source_not_whitelisted")
        return kept

    async def update_price_feeds(self, entries: List[Entry]) -> Optional[Dict]:
        """
        Push the entries passed as parameter with the internal pragma client.
        """
        if len(entries) == 0:
            return None

        await self.refresh_allowed_sources()
        entries = self.filter_allowed_sources(entries)
        if len(entries) == 0:
            logger.warning("⚠️ PUSHER: nothing left to push after the source whitelist")
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

            # Miden publishing is fully decoupled from the Starknet tick — it
            # runs on its own periodic loop (Orchestrator._miden_service) so it
            # can publish at a much higher cadence than Starknet pushes.
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
                # This fatal guard crashes the pod so k8s restarts it when the
                # Starknet publish path is persistently broken. But when Miden
                # publishing is enabled it shares this process, so crashing here
                # would also take down the independent Miden loop. In that case,
                # log and keep the loop retrying instead: the Starknet path
                # self-heals once the condition clears (e.g. the publisher
                # account is refunded), and Miden keeps publishing throughout.
                if self.miden_client is not None:
                    logger.error(
                        f"⛔ PUSHER: Starknet publish still failing after "
                        f"{self.consecutive_push_error} consecutive errors "
                        "— keeping the process alive so Miden publishing continues."
                    )
                    return None
                raise ValueError(
                    f"⛔ PUSHER: Failed to publish entries {self.consecutive_push_error} "
                    "times in a row. Something is wrong!"
                )

            return None

    async def publish_to_miden(self, entries: List[Entry]) -> None:
        """
        Publish the latest prices to Miden in a single batched transaction.

        Fully isolated — any failure here has zero impact on the Starknet loop.
        Called serially by the orchestrator's periodic Miden loop (no overlap),
        so no in-flight guard is needed here.
        """
        if self.miden_client is None or not entries:
            return
        # Pragma emits one entry per (pair, source); Miden has no notion of
        # "source" (publish_entry overwrites the storage map at faucet_id), and
        # the prover cost grows with the number of publish_entry calls. Aggregate
        # one MidenEntry per pair using the median price (matches Pragma's
        # on-chain aggregation).
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
        try:
            results = await self.miden_client.publish_entries(miden_entries)
            ok = sum(results)
            logger.info(f"🌐 MIDEN: published {ok}/{len(miden_entries)} entries")
            # Count Miden pushes toward liveness too. The health server is
            # otherwise driven only by Starknet pushes, so if the Starknet path
            # stops (e.g. out of funds) the liveness probe goes stale and k8s
            # restarts the pod — which would kill this Miden loop. A live Miden
            # feed keeps the pod healthy on its own.
            if ok > 0 and self.on_successful_push:
                self.on_successful_push()
        except Exception as e:
            logger.error(f"🌐 MIDEN: publish failed (Starknet unaffected): {e}")
