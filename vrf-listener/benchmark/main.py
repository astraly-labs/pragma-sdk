import asyncio
import click

from typing import Literal, Optional

from pydantic import HttpUrl
from pragma_sdk.onchain.constants import RPC_URLS

from benchmark.devnet.container import DEVNET_PORT
from benchmark.config.accounts_config import AccountsConfig, DEVNET_PREDEPLOYED_ACCOUNTS_CONFIG
from benchmark.stress.stress_tester import StressTester


async def main(
    network: Literal["devnet", "mainnet", "sepolia"],
    rpc_url: HttpUrl,
    accounts_config: AccountsConfig,
    txs_per_user: int,
    oracle_address: Optional[str] = None,
):
    stress_tester = StressTester(
        network=network,
        accounts_config=accounts_config,
        rpc_url=rpc_url,
        txs_per_user=txs_per_user,
        oracle_address=oracle_address,
    )

    if network == "devnet":
        await stress_tester.run_devnet_stresstest()
    else:
        await stress_tester.run_stresstest()


@click.command()
@click.option(
    "-n",
    "--network",
    required=True,
    type=click.Choice(["devnet", "sepolia", "mainnet"], case_sensitive=False),
    help="Which network to listen. Defaults to SEPOLIA.",
)
@click.option(
    "--rpc-url",
    type=click.STRING,
    required=False,
    help="RPC url used by the onchain client.",
)
@click.option(
    "-o",
    "--oracle-address",
    type=click.STRING,
    required=False,
    help="Address of the VRF contract",
)
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    required=False,
    help="Path to YAML accounts configuration file. Contains the accounts to use.",
)
@click.option(
    "--txs-per-user",
    type=click.IntRange(min=1),
    required=False,
    default=10,
    help="VRF requests sent per user.",
)
def cli_entrypoint(
    network: Literal["devnet", "mainnet", "sepolia"],
    rpc_url: Optional[HttpUrl],
    oracle_address: Optional[str],
    config_file: Optional[str],
    txs_per_user: int,
):
    """
    VRF Benchmark entry point.
    """
    if network == "devnet":
        rpc_url = f"http://127.0.0.1:{DEVNET_PORT}"
        accounts_config = DEVNET_PREDEPLOYED_ACCOUNTS_CONFIG
    else:
        if config_file is None:
            raise click.UsageError(
                '⛔ --config-file (-c) is required when --network is either "mainnet" or "sepolia".'
            )
        if oracle_address is None:
            raise click.UsageError(
                '⛔ --oracle-address (-o) is required when --network is either "mainnet" or "sepolia".'
            )
        accounts_config = AccountsConfig.from_yaml(config_file)

        if rpc_url is None:
            rpc_url = RPC_URLS[network][0]

    print(f"[BENCHMARK] 🔫 Gonna send {txs_per_user} VRF request per user")

    asyncio.run(
        main(
            network=network,
            rpc_url=rpc_url,
            accounts_config=accounts_config,
            txs_per_user=txs_per_user,
            oracle_address=oracle_address,
        )
    )


if __name__ == "__main__":
    cli_entrypoint()
