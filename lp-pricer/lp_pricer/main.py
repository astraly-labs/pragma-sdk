import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, List
from starknet_py.contract import InvokeResult

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.fetcher import LPFetcher
from pragma_sdk.common.fetchers.generic_fetchers.lp_fetcher.redis_manager import LpRedisManager
from pragma_sdk.common.exceptions import PublisherFetchError

from pragma_sdk.onchain.types.types import PrivateKey, NetworkName
from pragma_sdk.onchain.client import PragmaOnChainClient

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from lp_pricer.configs.pools_config import PoolsConfig

logger = logging.getLogger(__name__)

# This constant is tied to the `MINIMUM_DATA_POINTS` constant in the SDK.
# We should not update it alone! And this should not be configurable, since
# we want 10 data points to be equals to 30 minutes.
DELAY_BETWEEN_PUBLISH_IN_SECONDS = 180  # 3 minutes


async def wait_for_txs_acceptance(invocations: List[InvokeResult]):
    """
    Wait for all the transactions in the passed list to be accepted on-chain.
    Raises an error if one transaction is not accepted.
    """
    for invocation in invocations:
        nonce = invocation.invoke_transaction.nonce
        logger.info(f"  ⏳ waiting for TX {hex(invocation.hash)} (nonce={nonce}) to be accepted...")
        await invocation.wait_for_acceptance(check_interval=1)


async def main(
    pools_config: PoolsConfig,
    network: NetworkName,
    redis_host: str,
    publisher_name: str,
    publisher_address: str,
    private_key: PrivateKey,
    rpc_url: Optional[HttpUrl] = None,
    publish_delay: int = DELAY_BETWEEN_PUBLISH_IN_SECONDS,
) -> None:
    logger.info("🔨 Setting up clients and Redis connection...")
    pragma_client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=publisher_address,
        account_private_key=private_key,
    )

    # TODO(akhercha): Handle production mode
    # https://redis.io/docs/latest/develop/connect/clients/python/
    redis_host, redis_port = redis_host.split(":")
    redis_manager = LpRedisManager(host=redis_host, port=redis_port)

    fetcher_client = FetcherClient()
    lp_fetcher = LPFetcher(
        network=network,
        pairs=pools_config.get_all_pools(),
        publisher=publisher_name,
        redis_manager=redis_manager,
    )
    await lp_fetcher.validate_pools()
    fetcher_client.add_fetcher(lp_fetcher)

    logger.info(f"🧩 Starting the LP pricer for {network}...\n")
    while True:
        entries = await fetcher_client.fetch(return_exceptions=True)
        valid_entries = 0
        for entry in entries:
            if isinstance(entry, PublisherFetchError):
                logger.error(f"⛔ {entry}")
            else:
                valid_entries += 1

        if valid_entries > 0:
            logger.info(f"📨 Publishing LP prices for {valid_entries} pools...")
            try:
                invokes = await pragma_client.publish_many(entries)  # type:ignore[arg-type]
                await wait_for_txs_acceptance(invokes)
                logger.info("✅ Published complete!")
            except Exception as e:
                logger.error(e)

        await asyncio.sleep(publish_delay)


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
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to YAML configuration file.",
)
@click.option(
    "-n",
    "--network",
    required=True,
    default="sepolia",
    type=click.Choice(
        ["sepolia", "mainnet", "devnet", "pragma_devnet"],
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
    help="Name of the publisher of the LP Pricer.",
)
@click.option(
    "--publisher-address",
    type=click.STRING,
    required=True,
    help="Address of the publisher of the LP Pricer.",
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
    "--publish-delay",
    type=click.INT,
    required=False,
    default=DELAY_BETWEEN_PUBLISH_IN_SECONDS,
    help="Delay between each publish in seconds.",
)
def cli_entrypoint(
    log_level: str,
    config_file: str,
    network: NetworkName,
    redis_host: str,
    rpc_url: Optional[HttpUrl],
    publisher_name: str,
    publisher_address: str,
    raw_private_key: str,
    publish_delay: int,
) -> None:
    """
    Lp Pricer entry point.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(raw_private_key)
    pools_config = PoolsConfig.from_yaml(config_file)
    asyncio.run(
        main(
            pools_config=pools_config,
            network=network,
            redis_host=redis_host,
            rpc_url=rpc_url,
            publisher_name=publisher_name.upper(),
            publisher_address=publisher_address,
            private_key=private_key,
            publish_delay=publish_delay,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
