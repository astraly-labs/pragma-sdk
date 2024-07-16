import asyncio
import click
import logging

from pydantic import HttpUrl
from typing import Optional, Literal

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types import ContractAddresses

from checkpoint_setter.configs.pairs_config import PairsConfig

logger = logging.getLogger(__name__)

SECONDS_IN_ONE_MINUTE = 60


async def main(
    pairs_config: PairsConfig,
    network: Literal["mainnet", "sepolia"],
    oracle_address: str,
    admin_address: str,
    private_key: str,
    set_checkpoint_interval: int,
    rpc_url: Optional[HttpUrl] = None,
) -> None:
    pragma_client = PragmaOnChainClient(
        network=network if rpc_url is None else rpc_url,
        chain_name=network,
        account_contract_address=int(admin_address, 16),
        account_private_key=int(private_key, 16),
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=int(oracle_address, 16),
            summary_stats_address=0x0,
        ),
    )
    _log_handled_pairs(pairs_config, set_checkpoint_interval)
    logger.info("🧩 Starting Checkpoint setter...")
    tasks = [
        _set_checkpoints(pragma_client, pairs, pair_type)
        for pair_type, pairs in pairs_config
        if pairs
    ]
    try:
        while True:
            await asyncio.gather(*tasks)
            await asyncio.sleep(set_checkpoint_interval * SECONDS_IN_ONE_MINUTE)
    except asyncio.CancelledError:
        logger.info("... Checkpoint setter stopped!")
    except Exception as e:
        logger.error(f"Unexpected error in checkpoint setter: {e}")
        raise


def _log_handled_pairs(pairs_config: PairsConfig, set_checkpoint_interval: int) -> None:
    log_message = (
        "👇 New checkpoints will automatically be set every "
        f"{set_checkpoint_interval} minutes for those pairs:"
    )
    for pair_type, pairs in pairs_config:
        if pairs:
            log_message += f"\n{pair_type.upper()}: {pairs}"
    logger.info(log_message)


async def _set_checkpoints(client, pairs, checkpoint_type) -> None:
    try:
        if checkpoint_type == "spot":
            await client.set_checkpoints(pairs)
        elif checkpoint_type == "future":
            await client.set_future_checkpoints(pairs)
        logger.info(f"✅ Successfully set {checkpoint_type} checkpoints")
    except Exception as e:
        logger.error(f"⛔ Error while setting {checkpoint_type} checkpoint: {e}")


@click.command()
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to YAML configuration file.",
)
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
    help="Which network to listen. Defaults to SEPOLIA.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
)
@click.option(
    "--oracle-address",
    type=click.STRING,
    required=True,
    help="Address of the Pragma Oracle",
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
    "-t",
    "--set-checkpoint-interval",
    type=click.IntRange(min=0),
    required=False,
    default=60,
    help="Delay in minutes between checks for VRF requests. Defaults to 60 minutes.",
)
def cli_entrypoint(
    config_file: str,
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    rpc_url: Optional[HttpUrl],
    oracle_address: str,
    admin_address: str,
    private_key: str,
    set_checkpoint_interval: int,
) -> None:
    """
    Checkpoints setter entry point.
    """
    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(private_key)
    pairs_config = PairsConfig.from_yaml(config_file)
    asyncio.run(
        main(
            pairs_config=pairs_config,
            network=network,
            rpc_url=rpc_url,
            oracle_address=oracle_address,
            admin_address=admin_address,
            private_key=private_key,
            set_checkpoint_interval=set_checkpoint_interval,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
