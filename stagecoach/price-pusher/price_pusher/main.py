import click
import os
import logging

from typing import Optional, Union
from pragma.publisher.client import (
    PragmaOnChainClient,
    PragmaAPIClient,
    PragmaClient,
    PragmaPublisherClientT,
    FetcherClient,
)

from price_pusher.configs import PriceConfig
from price_pusher.utils.aws import fetch_aws_private_key


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
    setup_logging(log_level)
    private_key = load_private_key(private_key)
    client: Union[PragmaOnChainClient, PragmaAPIClient] = create_client(
        target=target,
        network=network,
        publisher_address=publisher_address,
        private_key=private_key,
        api_key=api_key,
        api_url=api_url,
    )
    price_config = PriceConfig.from_yaml(config_file)
    print(price_config)
    # Create & execute the client
    publisher_client = PragmaClient(client)
    fetcher_client = FetcherClient()
    # run_puller(target, net, keys, publisher)
    # run_pusher(target, net, keys, publisher)


def create_client(
    target: str,
    network: str,
    publisher_address: str,
    private_key: str,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
) -> Union[PragmaOnChainClient, PragmaAPIClient]:
    """
    Create the appropriate client based on the target.

    Args:
        target: The target type ('onchain' or 'offchain').
        network: The network type.
        publisher_address: The publisher's address.
        private_key: The private key for the account.
        api_key: The API key for offchain publishing.
        api_url: The API base URL for offchain publishing.

    Returns:
        Union[PragmaOnChainClient, PragmaAPIClient]
    """
    if target == "onchain":
        return PragmaOnChainClient(
            network=network,
            account_contract_address=publisher_address,
            account_private_key=private_key,
        )
    elif target == "offchain":
        if not api_key:
            raise click.BadParameter(
                "Argument api-key can't be None if offchain is selected"
            )
        if not api_url:
            raise click.BadParameter(
                "Argument api-url can't be None if offchain is selected"
            )
        return PragmaAPIClient(
            account_contract_address=publisher_address,
            account_private_key=private_key,
            api_key=api_key,
            api_base_url=api_url,
        )
    else:
        raise ValueError(f"Invalid target: {target}")


def setup_logging(log_level: str) -> None:
    """
    Set up the logging configuration based on the provided log level.

    Args:
        log_level: The logging level to set (e.g., "DEBUG", "INFO").
    """
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if numeric_log_level is None:
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(level=numeric_log_level)
    logger.setLevel(numeric_log_level)
    logging.getLogger().setLevel(numeric_log_level)


def load_private_key(private_key: str) -> str:
    """
    Load the private key either from AWS, environment variable, or from the provided plain value.

    Args:
        private_key: The private key string, either prefixed with 'aws:', 'plain:', or 'env:'.

    Returns:
        str
    """
    if private_key.startswith("aws:"):
        secret_name = private_key.split("aws:", 1)[1]
        return fetch_aws_private_key(secret_name)
    elif private_key.startswith("plain:"):
        return private_key.split("plain:", 1)[1]
    elif private_key.startswith("env:"):
        env_var_name = private_key.split("env:", 1)[1]
        return os.getenv(env_var_name)
    else:
        raise click.UsageError(
            "Private key must be prefixed with either 'aws:', 'plain:', or 'env:'"
        )


if __name__ == "__main__":
    main()
