import asyncio
import click
import logging

from typing import Optional, List

from pragma.publisher.client import FetcherClient, PragmaPublisherClientT

from price_pusher.core.poller import PricePoller
from price_pusher.core.listener import PriceListener
from price_pusher.core.request_handlers import REQUEST_HANDLER_REGISTRY
from price_pusher.core.pusher import PricePusher
from price_pusher.core.fetchers import add_all_fetchers
from price_pusher.configs.price_config import (
    PriceConfig,
)
from price_pusher.configs.cli import setup_logging, load_private_key, create_client
from price_pusher.orchestrator import Orchestrator
from price_pusher.type_aliases import Target, Network

logger = logging.getLogger(__name__)


async def main(
    price_configs: List[PriceConfig],
    target: Target,
    network: Network,
    private_key: str,
    publisher_name: str,
    publisher_address: str,
    api_base_url: Optional[str],
    api_key: Optional[str],
) -> None:
    """
    Main function of the price pusher.
    Create the parts that are then fed to the orchestrator for the main loop.
    """
    logger.info("🔨 Creating Pragma client...")
    pragma_client = create_client(
        target=target,
        network=network,
        publisher_address=publisher_address,
        private_key=private_key,
        api_base_url=api_base_url,
        api_key=api_key,
    )

    logger.info("🪚 Creating Fetcher client & adding fetchers...")
    fetcher_client = await add_all_fetchers(
        fetcher_client=FetcherClient(),
        publisher_name=publisher_name,
        price_configs=price_configs,
    )

    logger.info("⏳ Starting orchestration...")
    poller = PricePoller(fetcher_client=fetcher_client)
    pusher = PricePusher(client=pragma_client)
    orchestrator = Orchestrator(
        poller=poller,
        listeners=_create_listeners(price_configs, target, pragma_client),
        pusher=pusher,
    )

    logger.info("GO! Orchestration starting 🚀")
    await orchestrator.run_forever()


def _create_listeners(
    price_configs: List[PriceConfig],
    target: str,
    pragma_client: PragmaPublisherClientT,
) -> List[PriceListener]:
    """
    Create a listener for each price configuration. They will be used to monitor a group
    of pairs during the orchestration.
    """
    listeners: List[PriceListener] = []
    for price_config in price_configs:
        new_listener = PriceListener(
            request_handler=REQUEST_HANDLER_REGISTRY[target](client=pragma_client.client),
            price_config=price_config,
            polling_frequency_in_s=20,
        )
        listeners.append(new_listener)
    return listeners


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
    "-t",
    "--target",
    required=True,
    type=click.Choice(["onchain", "offchain"], case_sensitive=False),
    help="Where the prices will be published.",
)
@click.option(
    "-n",
    "--network",
    required=True,
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="At which network the price corresponds.",
)
@click.option(
    "-p",
    "--private-key",
    type=click.STRING,
    required=True,
    help="Secret key of the signer. Format: aws:secret_name, plain:secret_key, or env:ENV_VAR_NAME",
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
@click.option("--api-base-url", type=click.STRING, required=False, help="Pragma API base URL")
@click.option(
    "--api-key",
    type=click.STRING,
    required=False,
    help="Pragma API key used to publish offchain",
)
def cli_entrypoint(
    config_file: str,
    log_level: str,
    target: str,
    network: str,
    private_key: str,
    publisher_name: str,
    publisher_address: str,
    api_base_url: Optional[str],
    api_key: Optional[str],
) -> None:
    """
    Click does not support async functions.
    To make it work, we have to wrap the main function in this cli handler.

    Also handles basic checks/conversions from the CLI args.
    """
    if target == "offchain" and (not api_key or not api_base_url):
        raise click.UsageError("API key and API URL are required when destination is 'offchain'.")

    setup_logging(logger, log_level)
    private_key = load_private_key(private_key)
    price_configs: List[PriceConfig] = PriceConfig.from_yaml(config_file)

    # Make sure that the API base url does not ends with /
    if api_base_url is not None and api_base_url.endswith("/"):
        api_base_url = api_base_url.rstrip()[:-1]

    asyncio.run(
        main(
            price_configs,
            target,
            network,
            private_key,
            publisher_name,
            publisher_address,
            api_base_url,
            api_key,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
