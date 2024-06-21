import click
import logging

from typing import Optional, Union
from pragma.publisher.client import (
    PragmaOnChainClient,
    PragmaAPIClient,
    PragmaClient,
    PragmaPublisherClientT,
    FetcherClient,
)

from price_pusher.utils.cli import setup_logging, load_private_key, create_client
from price_pusher.configs import PriceConfig


logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    required=True,
    help="Path to config.yaml",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    help="Logging level",
)
@click.option(
    "-t",
    "--target",
    required=True,
    type=click.Choice(["onchain", "offchain"], case_sensitive=False),
    help="Where the prices will be published",
)
@click.option(
    "-n",
    "--network",
    required=True,
    type=click.Choice(["sepolia", "mainnet"], case_sensitive=False),
    help="At which network the price corresponds",
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
    help="Your publisher name",
)
@click.option(
    "--publisher-address",
    type=click.STRING,
    required=True,
    help="Your publisher address (required for onchain)",
)
@click.option(
    "--api-key",
    type=click.STRING,
    required=False,
    help="Pragma API key to publish offchain",
)
@click.option(
    "--api-url", type=click.STRING, required=False, help="Pragma API base URL"
)
def main(
    config_file: str,
    log_level: str,
    target: str,
    network: str,
    private_key: str,
    publisher_name: str,
    publisher_address: str,
    api_key: Optional[str],
    api_url: Optional[str],
) -> None:
    # Assert configuration is ok
    if target == "offchain" and (not api_key or not api_url):
        raise click.UsageError(
            "API key and API URL are required when destination is 'offchain'."
        )
    # Build needed parameters
    setup_logging(logger, log_level)
    private_key = load_private_key(private_key)
    _price_config = PriceConfig.from_yaml(config_file)
    # Create & execute the client
    client: Union[PragmaOnChainClient, PragmaAPIClient] = create_client(
        target=target,
        network=network,
        publisher_address=publisher_address,
        private_key=private_key,
        api_key=api_key,
        api_url=api_url,
    )
    publisher_client = PragmaClient(client)
    fetcher_client = FetcherClient()
    # run_puller(target, net, keys, publisher)
    # run_pusher(target, net, keys, publisher)


if __name__ == "__main__":
    main()
