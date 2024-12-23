import asyncio
import logging

from typing import Never, List
from starknet_py.contract import InvokeResult

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.generic_fetchers.deribit.fetcher import (
    DeribitOptionsFetcher,
)

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types.types import NetworkName


from merkle_maker.redis_manager import RedisManager

logger = logging.getLogger(__name__)

TIME_TO_SLEEP_BETWEEN_RETRIES = 3


class MerkleFeedPublisher:
    """
    Class responsible of querying the latest options, publishing them on-chain
    and in our Redis database.

    TODO: Implement automatic cleanup so we only keep the latest 100/1000 blocks?
    """

    network: NetworkName
    pragma_client: PragmaOnChainClient
    fetcher_client: FetcherClient
    redis_manager: RedisManager
    block_interval: int
    time_to_wait_between_block_number_polling: int

    def __init__(
        self,
        network: NetworkName,
        pragma_client: PragmaOnChainClient,
        fetcher_client: FetcherClient,
        redis_manager: RedisManager,
        block_interval: int = 1,
        time_to_wait_between_block_number_polling: int = 1,
    ):
        assert len(fetcher_client.fetchers) == 1
        assert isinstance(fetcher_client.fetchers[0], DeribitOptionsFetcher)

        self.network = network
        self.pragma_client = pragma_client
        self.fetcher_client = fetcher_client
        self.redis_manager = redis_manager
        self.block_interval = block_interval
        self.time_to_wait_between_block_number_polling = (
            time_to_wait_between_block_number_polling
        )

    @property
    def deribit_fetcher(self) -> DeribitOptionsFetcher:
        # We know for sure that fetchers[0] is DeribitOptionsFetcher, see assertions above.
        return self.fetcher_client.fetchers[0]  # type: ignore[return-value]

    async def publish_forever(self) -> Never:
        """
        Publish a new Merkle Feed on chain every [self.block_interval] block(s)
        forever.
        We store the merkle tree and the options used to generate the merkle root
        to a Redis database that will get consumed by our Rust services.
        """
        current_block = await self.pragma_client.get_block_number()
        while True:
            logger.info(f"Current block: {current_block}")

            if self._current_block_is_not_processed(current_block):
                try:
                    await self._publish_and_store(current_block=current_block)
                except Exception:
                    logger.error(
                        f"⛔ Publishing for block {current_block} failed. "
                        f"Retrying in {TIME_TO_SLEEP_BETWEEN_RETRIES} seconds...\n"
                    )
                    await asyncio.sleep(TIME_TO_SLEEP_BETWEEN_RETRIES)
                    continue
            else:
                logger.info(f"🫷 Block {current_block} is already processed!\n")

            next_block = current_block + self.block_interval
            logger.info(f"⏳ Waiting for block {next_block}...")

            while True:
                await asyncio.sleep(self.time_to_wait_between_block_number_polling)
                new_block = await self.pragma_client.get_block_number()
                if new_block >= next_block:
                    logger.info(f"⌛ ... reached block {new_block}!\n")
                    current_block = new_block
                    break

    async def _publish_and_store(
        self,
        current_block: int,
    ) -> None:
        """
        Retrieves the options from Deribit, publish the merkle root on-chain for
        the network and block_number.
        When done, store to Redis the merkle tree and the options used.
        """
        logger.info("🔍 Fetching the deribit options...")
        entries = await self.fetcher_client.fetch()
        logger.info("... fetched!")

        logger.info("🎣 Publishing the merkle root onchain...")
        invocations = await self.pragma_client.publish_many(entries)  # type: ignore[arg-type]
        await self._wait_for_txs_acceptance(invocations)
        logger.info("... published!")

        logger.info("🏭 Storing the merkle tree & options in Redis...")
        latest_data = self.deribit_fetcher.latest_data
        success_store = self.redis_manager.store_block_data(
            self.network, current_block, latest_data
        )
        if not success_store:
            raise RuntimeError(
                f"Could not store data for block {current_block} to Redis."
            )
        else:
            logger.info("... stored!")

        logger.info(f"✅ Block {current_block} done!\n")

    async def _wait_for_txs_acceptance(self, invocations: List[InvokeResult]):
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

    def _current_block_is_not_processed(
        self,
        block_number: int,
    ) -> bool:
        """
        Check if the current block is already processed.
        """
        latest_published_block = self.redis_manager.get_latest_published_block(
            self.network
        )
        if latest_published_block is None:
            return True
        return block_number > latest_published_block
