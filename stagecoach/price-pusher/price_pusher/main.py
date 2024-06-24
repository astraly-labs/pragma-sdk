import click
import logging

from typing import Optional, Union, List
from pragma.publisher.client import (
    PragmaOnChainClient,
    PragmaAPIClient,
    PragmaClient,
    FetcherClient,
)
from price_pusher.core.poller import PricePoller
from price_pusher.core.listener import ChainPriceListener
from price_pusher.core.pusher import PricePusher

from price_pusher.configs.price_config import PriceConfig
from price_pusher.configs.cli import setup_logging, load_private_key, create_client

import queue


logger = logging.getLogger(__name__)

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
@click.option(
    "--api-base-url", type=click.STRING, required=False, help="Pragma API base URL"
)
@click.option(
    "--api-key",
    type=click.STRING,
    required=False,
    help="Pragma API key used to publish offchain",
)
def main(
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
    # Assert configuration is ok
    if target == "offchain" and (not api_key or not api_base_url):
        raise click.UsageError(
            "API key and API URL are required when destination is 'offchain'."
        )
    # Build needed parameters
    setup_logging(logger, log_level)
    private_key = load_private_key(private_key)
    price_config: List[PriceConfig] = PriceConfig.from_yaml(config_file)
    print(price_config)
    # Create & execute the client
    client: Union[PragmaOnChainClient, PragmaAPIClient] = create_client(
        target=target,
        network=network,
        publisher_address=publisher_address,
        private_key=private_key,
        api_base_url=api_base_url,
        api_key=api_key,
    )
    _publisher_client = PragmaClient(client)
    fetcher_client = FetcherClient()
    # todo : add fetchers in client

    _poller = PricePoller(fetcher_client)
    _listener = ChainPriceListener()
    _pusher = PricePusher()
    
    # main loop
    entries_queue = queue.Queue()
    # Retrieve data from poller
    # Filter data with listener
    # if data is worth pushing
        # push filtered data with pusher

    # Drop useless entries (max queue size or used data)


if __name__ == "__main__":
    main()
