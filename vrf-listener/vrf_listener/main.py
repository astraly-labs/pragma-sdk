import asyncio
import click
import os
import logging

from pydantic import HttpUrl
from typing import Optional, Literal

from pragma_utils.logger import setup_logging
from pragma_utils.cli import load_private_key_from_cli_arg
from pragma_sdk.onchain.types import ContractAddresses
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.common.logging import get_pragma_sdk_logger

from vrf_listener.safe_queue import ThreadSafeQueue
from vrf_listener.indexer import Indexer
from vrf_listener.listener import Listener

logger = logging.getLogger(__name__)


# Related to Apibara GRPC - need to disable fork support because of async.
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"


async def main(
    network: Literal["mainnet", "sepolia"],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    check_requests_interval: int,
    ignore_request_threshold: int,
    rpc_url: Optional[HttpUrl] = None,
    index_with_apibara: bool = False,
    apibara_api_key: Optional[str] = None,
) -> None:
    logger.info("🧩 Starting VRF listener...")

    client = _create_pragma_client(
        network=network,
        vrf_address=vrf_address,
        admin_address=admin_address,
        private_key=private_key,
        rpc_url=rpc_url,
    )

    requests_queue = ThreadSafeQueue()

    if index_with_apibara:
        indexer = await Indexer.from_client(
            pragma_client=client,
            apibara_api_key=apibara_api_key,
            requests_queue=requests_queue,
            ignore_request_threshold=ignore_request_threshold,
        )
        asyncio.create_task(indexer.run_forever())

    listener = Listener(
        pragma_client=client,
        private_key=private_key,
        requests_queue=requests_queue,
        check_requests_interval=check_requests_interval,
        ignore_request_threshold=ignore_request_threshold,
        indexer=indexer if index_with_apibara else None,
    )

    await listener.run_forever()


def _create_pragma_client(
    network: Literal["mainnet", "sepolia"],
    vrf_address: str,
    admin_address: str,
    private_key: str,
    rpc_url: Optional[HttpUrl] = None,
) -> PragmaOnChainClient:
    """
    Creates the Pragma Client & init the VRF contract.
    """
    client = PragmaOnChainClient(
        chain_name=network,
        network=network if rpc_url is None else rpc_url,
        account_contract_address=admin_address,
        account_private_key=private_key,
        contract_addresses_config=ContractAddresses(
            publisher_registry_address=0x0,
            oracle_proxy_addresss=0x0,
            summary_stats_address=0x0,
        ),
    )
    client.init_randomness_contract(int(vrf_address, 16))
    return client


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
    "raw_private_key",
    type=click.STRING,
    required=True,
    help=(
        "Private key of the signer. Format: "
        "aws:secret_name, "
        "plain:private_key, "
        "or env:ENV_VAR_NAME"
    ),
)
@click.option(
    "-t",
    "--check-requests-interval",
    type=click.IntRange(min=0),
    required=False,
    default=10,
    help="Delay in seconds between checks for VRF requests. Defaults to 10 seconds.",
)
@click.option(
    "--ignore-request-threshold",
    type=click.IntRange(min=0),
    required=False,
    default=3,
    help="Blocks to ignore before the current block for the handling.",
)
@click.option(
    "--index-with-apibara",
    type=click.BOOL,
    is_flag=True,
    required=False,
    default=False,
    help="Self index the VRF requests using Apibara instead of using Starknet.py",
)
@click.option(
    "--apibara-api-key",
    type=click.STRING,
    required=False,
    help="Apibara API key. Needed when indexing with Apibara.",
)
def cli_entrypoint(
    log_level: str,
    network: Literal["mainnet", "sepolia"],
    rpc_url: Optional[HttpUrl],
    vrf_address: str,
    admin_address: str,
    raw_private_key: str,
    check_requests_interval: int,
    ignore_request_threshold: int,
    index_with_apibara: bool,
    apibara_api_key: Optional[str],
) -> None:
    """
    VRF Listener entry point.
    """
    setup_logging(logger, log_level)
    pragma_sdk_logger = get_pragma_sdk_logger()
    pragma_sdk_logger.setLevel(log_level)

    private_key = load_private_key_from_cli_arg(raw_private_key)

    if isinstance(private_key, tuple):
        raise click.UsageError("⛔ KeyStores aren't supported as private key for the vrf-listener!")

    if index_with_apibara and apibara_api_key is None:
        raise click.UsageError(
            "⛔ Apibara API Key is needed when --index-with-apibara is provided."
        )

    asyncio.run(
        main(
            network=network,
            rpc_url=rpc_url,
            vrf_address=vrf_address,
            admin_address=admin_address,
            private_key=private_key,
            check_requests_interval=check_requests_interval,
            ignore_request_threshold=ignore_request_threshold,
            index_with_apibara=index_with_apibara,
            apibara_api_key=apibara_api_key,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
