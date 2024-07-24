import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, Literal, Tuple

from pragma_sdk.onchain.client import PragmaOnChainClient

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

logger = logging.getLogger(__name__)


async def main(
    network: Literal["mainnet", "sepolia"],
    redis_host: str,
    publisher_address: str,
    private_key: str | Tuple[str, str],
    block_interval: int,
    rpc_url: Optional[HttpUrl] = None,
) -> None:
    logger.info("🧩 Starting the Merkle Maker...")
    _client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=publisher_address,
        account_private_key=private_key,
    )


@click.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False),
    help="Logging level.",
)
@click.option(
    "-n",
    "--network",
    required=True,
    default="sepolia",
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="On which networks the checkpoints will be set.",
)
@click.option(
    "--redis-host",
    type=click.STRING,
    required=False,
    default="localhost:6379",
    help="Host where the Redis service is live.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
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
    help="Delay in block between each new Merkle Feed.",
)
def cli_entrypoint(
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    redis_host: str,
    rpc_url: Optional[HttpUrl],
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
            publisher_address=publisher_address,
            private_key=private_key,
            block_interval=block_interval,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
