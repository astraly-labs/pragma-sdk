import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, Literal, Tuple, Never

from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.generic_fetchers.deribit import DeribitOptionsFetcher

from pragma_sdk.onchain.client import PragmaOnChainClient

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from merkle_maker.redis import RedisManager

logger = logging.getLogger(__name__)

TIME_TO_WAIT_BETWEEN_BLOCK_NUMBER_POLLING = 2


async def main(
    network: Literal["mainnet", "sepolia"],
    redis_host: str,
    publisher_name: str,
    publisher_address: str,
    private_key: str | Tuple[str, str],
    block_interval: int,
    rpc_url: Optional[HttpUrl] = None,
) -> None:
    logger.info("🔨 Setting up clients and Redis connection...")
    pragma_client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=publisher_address,
        account_private_key=private_key,
    )

    redis_host, redis_port = redis_host.split(":")
    redis_manager = RedisManager(host=redis_host, port=redis_port)

    fetcher_client = FetcherClient()
    deribit_fetcher = DeribitOptionsFetcher(
        pairs=[
            Pair.from_tickers("BTC", "USD"),  # type: ignore[list-item]
            Pair.from_tickers("ETH", "USD"),  # type: ignore[list-item]
        ],
        publisher=publisher_name,
    )
    fetcher_client.add_fetcher(deribit_fetcher)

    logger.info("🧩 Starting the Merkle Maker...")
    await _publish_merkle_feeds_forever(
        pragma_client=pragma_client,
        fetcher_client=fetcher_client,
        redis_manager=redis_manager,
        block_interval=block_interval,
    )


async def _publish_merkle_feeds_forever(
    pragma_client: PragmaOnChainClient,
    fetcher_client: FetcherClient,
    redis_manager: RedisManager,
    block_interval: int,
) -> Never:
    """
    Publish a new Merkle Feed on chain every [block_interval] block(s) forever.
    We store the merkle tree and the options used to generate the merkle root
    to a Redis database that will get consumed by our Rust service.
    """
    deribit_fetcher: DeribitOptionsFetcher = fetcher_client.fetchers[0]  # type: ignore[assignment]
    while True:
        current_block = await pragma_client.get_block_number()
        logger.info(f"Current block: {current_block}")

        logger.info("🔍 Fetching the deribit options...")
        entries = await fetcher_client.fetch()

        # TODO: move this block in another thread so we loose 0 time on this?
        logger.info("🏭 Storing the merkle tree & options in Redis...")
        redis_manager.store_latest_data(deribit_fetcher.get_latest_data())
        logger.info("... done!")

        logger.info("🎣 Publishing the merkle root onchain...")
        try:
            await pragma_client.publish_entries(entries)  # type: ignore[arg-type]
            logger.info("... done!")
        except Exception:
            # TODO: remove this part when the contract has been updated
            logger.warning("Could not publish! Contract not yet updated.")

        next_block = current_block + block_interval
        logger.info(f"⏳ Waiting for block {next_block}...")

        while True:
            await asyncio.sleep(TIME_TO_WAIT_BETWEEN_BLOCK_NUMBER_POLLING)
            new_block = await pragma_client.get_block_number()
            if new_block >= next_block:
                logger.info(f"⌛ ... reached block {new_block}!\n")
                break


@click.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        case_sensitive=False,
    ),
    help="Logging level.",
)
@click.option(
    "-n",
    "--network",
    required=True,
    default="sepolia",
    type=click.Choice(
        ["sepolia", "mainnet"],
        case_sensitive=False,
    ),
    help="On which networks the checkpoints will be set.",
)
@click.option(
    "--redis-host",
    type=click.STRING,
    required=False,
    default="localhost:6379",
    help="Host where the Redis service is live. Format is HOST:PORT, example: localhost:6379",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
)
@click.option(
    "--publisher-name",
    type=click.STRING,
    required=True,
    help="Name of the publisher of the Merkle Feed.",
)
@click.option(
    "--publisher-address",
    type=click.STRING,
    required=True,
    help="Address of the publisher of the Merkle Feed.",
)
@click.option(
    "-p",
    "--private-key",
    "raw_private_key",
    type=click.STRING,
    required=True,
    help=(
        "Private key of the publisher. Format: "
        "aws:secret_name, "
        "plain:private_key, "
        "env:ENV_VAR_NAME, "
        "or keystore:PATH/TO/THE/KEYSTORE:PASSWORD"
    ),
)
@click.option(
    "-b",
    "--block-interval",
    type=click.IntRange(min=1),
    required=False,
    default=1,
    help="Delay in block between each new Merkle Feed is published.",
)
def cli_entrypoint(
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    redis_host: str,
    rpc_url: Optional[HttpUrl],
    publisher_name: str,
    publisher_address: str,
    raw_private_key: str,
    block_interval: int,
) -> None:
    """
    Merkle Maker entry point.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(raw_private_key)
    asyncio.run(
        main(
            network=network,
            redis_host=redis_host,
            rpc_url=rpc_url,
            publisher_name=publisher_name.upper(),
            publisher_address=publisher_address,
            private_key=private_key,
            block_interval=block_interval,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
