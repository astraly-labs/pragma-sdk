import asyncio
import click
import logging

from typing import Optional, List, Sequence

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.types.client import PragmaClient
from pragma_sdk.common.logging import get_pragma_sdk_logger

from pragma_sdk.onchain.types.types import PrivateKey
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_sdk.onchain.client import PragmaOnChainClient

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg

from price_pusher.core.poller import PricePoller
from price_pusher.core.listener import PriceListener
from price_pusher.core.request_handlers.chain import ChainRequestHandler
from price_pusher.core.pusher import PricePusher
from price_pusher.core.fetchers import add_all_fetchers
from price_pusher.configs.price_config import (
    PriceConfig,
)
from price_pusher.orchestrator import Orchestrator
from price_pusher.price_types import Network
from price_pusher.health_server import HealthServer

logger = logging.getLogger(__name__)


async def main(
    price_configs: List[PriceConfig],
    network: Network,
    private_key: PrivateKey,
    publisher_name: str,
    publisher_address: str,
    poller_refresh_interval: int,
    rpc_url: Optional[str] = None,
    max_fee: Optional[int] = None,
    pagination: Optional[int] = None,
    enable_strk_fees: Optional[bool] = None,
    health_port: Optional[int] = None,
    max_seconds_without_push: Optional[int] = None,
    evm_rpc_urls: Optional[List[str]] = None,
) -> None:
    """
    Main function of the price pusher.
    Create the parts that are then fed to the orchestrator for the main loop.
    """
    logger.info("🔨 Creating Pragma client...")
    pragma_client = _create_client(
        network=network,
        publisher_address=publisher_address,
        private_key=private_key,
        rpc_url=rpc_url,
        max_fee=max_fee,
        pagination=pagination,
        enable_strk_fees=enable_strk_fees,
    )

    logger.info("🪚 Creating Fetcher client & adding fetchers...")
    fetcher_client = add_all_fetchers(
        fetcher_client=FetcherClient(),
        publisher_name=publisher_name,
        price_configs=price_configs,
        evm_rpc_urls=evm_rpc_urls,
    )

    logger.info("⏳ Starting orchestration...")

    # Create health server if configured
    health_server = None
    if health_port:
        health_server = HealthServer(
            port=health_port, max_seconds_without_push=max_seconds_without_push or 300
        )

    poller = PricePoller(fetcher_client=fetcher_client)
    pusher = PricePusher(
        client=pragma_client,
        on_successful_push=health_server.update_last_push if health_server else None,
    )
    orchestrator = Orchestrator(
        poller=poller,
        poller_refresh_interval=poller_refresh_interval,
        listeners=_create_listeners(price_configs, pragma_client),
        pusher=pusher,
        health_server=health_server,
    )

    logger.info("🚀 Orchestration starting 🚀")
    await orchestrator.run_forever()


def _create_listeners(
    price_configs: List[PriceConfig],
    pragma_client: PragmaClient,
) -> List[PriceListener]:
    """
    Create a listener for each price configuration. They will be used to monitor a group
    of pairs during the orchestration.
    """
    listeners: List[PriceListener] = []
    for price_config in price_configs:
        new_listener = PriceListener(
            request_handler=ChainRequestHandler(client=pragma_client),
            price_config=price_config,
            polling_frequency_in_s=20,
        )
        listeners.append(new_listener)
    return listeners


def _create_client(
    network: Network,
    publisher_address: str,
    private_key: PrivateKey,
    rpc_url: Optional[str] = None,
    max_fee: Optional[int] = None,
    pagination: Optional[int] = None,
    enable_strk_fees: Optional[bool] = None,
) -> PragmaClient:
    """Create the on-chain client used by the pusher."""

    execution_config = ExecutionConfig(
        pagination=pagination if pagination is not None else ExecutionConfig.pagination,
        max_fee=max_fee if max_fee is not None else ExecutionConfig.max_fee,
        enable_strk_fees=enable_strk_fees
        if enable_strk_fees is not None
        else ExecutionConfig.enable_strk_fees,
        auto_estimate=True,
    )
    return PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=publisher_address,
        account_private_key=private_key,
        execution_config=execution_config,
    )


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
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
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
    help="RPC url used to interact with the chain.",
)
@click.option(
    "-p",
    "--private-key",
    "raw_private_key",
    type=click.STRING,
    required=True,
    help=(
        "Private key of the signer. Format: "
        "aws:secret_name, "
        "plain:private_key, "
        "env:ENV_VAR_NAME, "
        "or keystore:PATH/TO/THE/KEYSTORE:PASSWORD"
    ),
)
@click.option(
    "--publisher-name",
    type=click.STRING,
    required=True,
    help="Your publisher name.",
)
@click.option(
    "--publisher-address",
    type=click.STRING,
    required=True,
    help="Your publisher address.",
)
@click.option(
    "--max-fee",
    type=click.IntRange(min=0),
    required=False,
    help="Max fee used when using the onchain client",
)
@click.option(
    "--pagination",
    type=click.IntRange(min=0),
    required=False,
    help="Number of elements per page returned from the onchain client",
)
@click.option(
    "--enable-strk-fees",
    type=click.BOOL,
    required=False,
    help="Pay fees using STRK for on chain queries.",
)
@click.option(
    "--poller-refresh-interval",
    type=click.IntRange(min=5),
    required=False,
    default=5,
    help="Interval in seconds between poller refreshes. Default to 5 seconds.",
)
@click.option(
    "--health-port",
    type=click.IntRange(min=1, max=65535),
    required=False,
    default=8080,
    help="Port for health check HTTP server. Default to 8080. Set to 0 to disable.",
)
@click.option(
    "--max-seconds-without-push",
    type=click.IntRange(min=60),
    required=False,
    default=300,
    help="Maximum seconds without push before unhealthy. Default to 300 seconds (5 minutes).",
)
@click.option(
    "--evm-rpc-url",
    type=click.STRING,
    multiple=True,
    help="Ethereum RPC URL used by on-chain fetchers (can be passed multiple times).",
)
def cli_entrypoint(
    config_file: str,
    log_level: str,
    network: str,
    rpc_url: Optional[str],
    raw_private_key: str,
    publisher_name: str,
    publisher_address: str,
    max_fee: Optional[int],
    pagination: Optional[int],
    enable_strk_fees: Optional[bool],
    poller_refresh_interval: int,
    health_port: Optional[int],
    max_seconds_without_push: Optional[int],
    evm_rpc_url: Sequence[str],
) -> None:
    if rpc_url and not rpc_url.startswith("http"):
        raise click.UsageError(
            '⛔ "rpc_url" format is incorrect. It must start with http(...)'
        )
    for url in evm_rpc_url:
        if not url.startswith("http"):
            raise click.UsageError(
                '⛔ "evm-rpc-url" format is incorrect. Each value must start with http(...)'
            )

    # Update the logger level of the pragma_sdk package
    sdk_logger = get_pragma_sdk_logger()
    sdk_logger.setLevel(log_level)

    setup_logging(logger, log_level)
    private_key = load_private_key_from_cli_arg(raw_private_key)
    price_configs: List[PriceConfig] = PriceConfig.from_yaml(config_file)

    # Disable health server if port is 0
    if health_port == 0:
        health_port = None

    evm_rpc_urls = list(evm_rpc_url) if evm_rpc_url else None

    asyncio.run(
        main(
            price_configs=price_configs,
            network=network,
            private_key=private_key,
            publisher_name=publisher_name.upper(),
            publisher_address=publisher_address,
            rpc_url=rpc_url,
            max_fee=max_fee,
            pagination=pagination,
            enable_strk_fees=enable_strk_fees,
            poller_refresh_interval=poller_refresh_interval,
            health_port=health_port,
            max_seconds_without_push=max_seconds_without_push,
            evm_rpc_urls=evm_rpc_urls,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
