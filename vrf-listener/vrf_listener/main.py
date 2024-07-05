import asyncio
import click
import logging

from typing import Optional

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

logger = logging.getLogger(__name__)


async def main():
    pass
    # client = PragmaOnChainClient(
    #     network=RPC_URL,
    #     account_private_key=admin_private_key,
    #     account_contract_address=ADMIN_CONTRACT_ADDRESS,
    #     chain_name=NETWORK,
    # )
    # client.init_randomness_contract(VRF_CONTRACT_ADDRESS)

    # while True:
    #     logger.info("Checking for randomness requests...")
    #     try:
    #         await client.handle_random(admin_private_key, START_BLOCK)
    #     except Exception as e:
    #         logger.error("Error handling randomness requests: %s", e)
    #     await asyncio.sleep(VRF_UPDATE_TIME_SECONDS)


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
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="At which network the price corresponds.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
)
@click.option(
    "-v",
    "--vrf-address",
    type=click.STRING,
    required=True,
    help="Address of the VRF contract",
)
@click.option(
    "-a",
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
    "--start-block",
    type=click.INT,
    required=False,
    default=0,
    help="At which block to start listening for VRF requests. Defaults to 0.",
)
def cli_entrypoint(
    log_level: str,
    network: str,
    rpc_url: Optional[str],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    start_block: int,
) -> None:
    """
    Click does not support async functions.
    To make it work, we have to wrap the main function in this cli handler.

    Also handles basic checks/conversions from the CLI args.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(private_key)

    asyncio.run(main())


if __name__ == "__main__":
    cli_entrypoint()
