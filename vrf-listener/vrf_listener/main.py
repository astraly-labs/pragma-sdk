import asyncio
import click
import logging

from typing import Optional

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from pragma_sdk.onchain.client import PragmaOnChainClient

logger = logging.getLogger(__name__)


async def main(
    network: str,
    rpc_url: Optional[str],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    start_block: int,
    update_time_interval: int,
) -> None:
    client = PragmaOnChainClient(
        network=rpc_url,
        account_contract_address=admin_address,
        account_private_key=private_key,
        chain_name=network,
    )
    client.init_randomness_contract(vrf_address)

    while True:
        logger.info("Checking for randomness requests...")
        try:
            await client.handle_random(private_key, start_block)
        except Exception as e:
            logger.error("Error handling randomness requests: %s", e)
        await asyncio.sleep(update_time_interval)


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
    required=False,
    default="sepolia",
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="Which network to listen. Defaults to SEPOLIA.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
)
@click.option(
    "--vrf-address",
    type=click.STRING,
    required=True,
    help="Address of the VRF contract",
)
@click.option(
    "--admin-address",
    type=click.STRING,
    required=True,
    help="Address of the Admin contract",
)
@click.option(
    "-p",
    "--private-key",
    type=click.STRING,
    required=True,
    help="Secret key of the signer. Format: aws:secret_name, plain:secret_key, or env:ENV_VAR_NAME",
)
@click.option(
    "-b" "--start-block",
    type=click.INT,
    required=False,
    default=0,
    help="At which block to start listening for VRF requests. Defaults to 0.",
)
@click.option(
    "-t" "--update-time-interval",
    type=click.INT,
    required=False,
    default=10,
    help="Delay in seconds between VRF checks. Defaults to 10 seconds.",
)
def cli_entrypoint(
    log_level: str,
    network: str,
    rpc_url: Optional[str],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    start_block: int,
    update_time_interval: int,
) -> None:
    """
    Click does not support async functions.
    To make it work, we have to wrap the main function in this cli handler.

    Also handles basic checks/conversions from the CLI args.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(private_key)

    asyncio.run(
        main(
            network,
            rpc_url,
            vrf_address,
            admin_address,
            private_key,
            start_block,
            update_time_interval,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
