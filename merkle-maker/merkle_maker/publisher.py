import asyncio
import logging

from typing import Literal, Never

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.generic_fetchers.deribit.fetcher import DeribitOptionsFetcher

from pragma_sdk.onchain.client import PragmaOnChainClient


from merkle_maker.redis import RedisManager

logger = logging.getLogger(__name__)

TIME_TO_WAIT_BETWEEN_BLOCK_NUMBER_POLLING = 1


class MerkleFeedPublisher:
    """
    Class responsible of querying the latest options, publishing them on-chain
    and in our Redis database.

    TODO: Implement automatic cleanup so we only keep the latest 100/1000 blocks?
    """

    network: Literal["mainnet", "sepolia"]
    pragma_client: PragmaOnChainClient
    fetcher_client: FetcherClient
    redis_manager: RedisManager
    block_interval: int
    time_to_wait_between_block_number_polling: int

    def __init__(
        self,
        network: Literal["mainnet", "sepolia"],
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
        self.time_to_wait_between_block_number_polling = time_to_wait_between_block_number_polling

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
        while True:
            current_block = await self.pragma_client.get_block_number()
            logger.info(f"Current block: {current_block}")

            if self._current_block_is_not_processed(current_block):
                await self._publish_and_store(current_block=current_block)
            else:
                logger.info(f"🫷 Block {current_block} is already processed!\n")

            next_block = current_block + self.block_interval
            logger.info(f"⏳ Waiting for block {next_block}...")

            while True:
                await asyncio.sleep(TIME_TO_WAIT_BETWEEN_BLOCK_NUMBER_POLLING)
                new_block = await self.pragma_client.get_block_number()
                if new_block >= next_block:
                    logger.info(f"⌛ ... reached block {new_block}!\n")
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

        logger.info("🎣 Publishing the merkle root onchain...")
        try:
            await self.pragma_client.publish_entries(entries)  # type: ignore[arg-type]
            logger.info("... done!")
        except Exception:
            # TODO: remove this part when the contract has been updated
            logger.warning("Could not publish! Contract not yet updated.")

        logger.info("🏭 Storing the merkle tree & options in Redis...")

        latest_data = self.deribit_fetcher.latest_data
        success_store = self.redis_manager.store_block_data(
            self.network, current_block, latest_data
        )
        if not success_store:
            raise RuntimeError(f"Could not store data for block {current_block} to Redis.")

        logger.info(f"✅ Block {current_block} done!\n")

    def _current_block_is_not_processed(
        self,
        block_number: int,
    ) -> bool:
        """
        Check if the current block is already processed, i.e if we already
        published a merkle root onchain and stored the data into Redis.
        """
        return all(
            [
                self.redis_manager.get_options(self.network, block_number) is None,
                self.redis_manager.get_merkle_tree(self.network, block_number) is None,
            ]
        )
