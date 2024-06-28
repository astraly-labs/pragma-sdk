import click
import os
import logging

from logging import Logger
from typing import Optional
from pragma.publisher.client import (
    PragmaClient,
    PragmaOnChainClient,
    PragmaAPIClient,
    PragmaClient,
)

from price_pusher.type_aliases import Target, Network
from price_pusher.utils.aws import fetch_aws_private_key


def create_client(
    target: Target,
    network: Network,
    publisher_address: str,
    private_key: str,
    api_base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> PragmaClient:
    """
    Create the appropriate client based on the target.

    Args:
        target: The target type ('onchain' or 'offchain').
        network: The network type.
        publisher_address: The publisher's address.
        private_key: The private key for the account.
        api_base_url: The API base URL for offchain publishing.
        api_key: The API key for offchain publishing.

    Returns:
        PragmaClient
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
        if not api_base_url:
            raise click.BadParameter(
                "Argument api-base-url can't be None if offchain is selected"
            )
        return PragmaAPIClient(
            account_contract_address=publisher_address,
            account_private_key=private_key,
            api_key=api_key,
            api_base_url=api_base_url,
        )
    else:
        raise ValueError(f"Invalid target: {target}")


def setup_logging(logger: Logger, log_level: str) -> None:
    """
    Set up the logging configuration based on the provided log level.

    Args:
        logger: The logger to update
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
