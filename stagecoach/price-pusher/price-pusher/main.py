import click
import logging
import re
from .config import read_price_config_file
from .utils import load_pvt_key_from_aws
from pragma.publisher.client import (
    PragmaOnChainClient,
    PragmaAPIClient,
    PragmaClient,
    PragmaPublisherClientT,
    FetcherClient,
)
from typing import Union

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_private_key(args):
    private_key_splitted = args.split(":")
    if len(private_key_splitted) != 2:
        raise click.BadParameter("private key parameter is not well formatted")
    if private_key_splitted[0] == "aws":
        return load_pvt_key_from_aws(private_key_splitted[1])
    elif private_key_splitted[0] == "plain":
        return private_key_splitted[1]
    else:
        raise click.BadParameter("not a valid private key format")


@click.command()
@click.option("--config-file", required=True, help="Path to config.yaml")
@click.option(
    "--log-level",
    default="INFO",
    help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option("--network", required=True, help="<onchain|offchain:sepolia|mainnet>")
@click.option("--private-key", required=True, help="<aws|plain:secret_name|value>")
@click.option("--publisher-name", required=True, help="Your publisher name")
@click.option("--publisher-address", required=True, help="Your publisher address")
@click.option("--api-key", default=None, help="pragma api key to publish offchain")
@click.option("--api-url", default=None, help="pragma api base url")
def main(
    log_level,
    config_file,
    network,
    private_key,
    publisher_name,
    publisher_address,
    api_key,
    api_url,
):
    numeric_log_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_log_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logger.setLevel(numeric_log_level)
    logging.getLogger().setLevel(numeric_log_level)

    config = read_price_config_file(config_file)
    print(config)

    if network and not re.match(r"^(onchain|offchain):(sepolia|mainnet)$", network):
        raise click.BadParameter(
            "Network must be in the format <onchain|offchain:sepolia|mainnet>"
        )

    target, net = network.split(":")

    key = get_private_key(private_key)

    client: PragmaPublisherClientT
    if target == "onchain":
        client = PragmaOnChainClient(
            network=net,
            account_contract_address=publisher_address,
            account_private_key=key,
        )
    elif target == "offchain":
        if api_key == None:
            raise click.BadParameter(
                "Argument api-key can't be None if offchain is selected"
            )
        if api_url == None:
            raise click.BadParameter(
                "Argument api-url can't be None if offchain is selected"
            )
        client = PragmaAPIClient(
            account_contract_address=publisher_address,
            account_private_key=private_key,
            api_key=api_key,
            api_base_url=api_url,
        )

    publisher_client = PragmaClient(client)

    fetcher_client = FetcherClient()

    # run_puller(target, net, keys, publisher)
    # run_pusher(target, net, keys, publisher)
    # run


if __name__ == "__main__":
    main()
