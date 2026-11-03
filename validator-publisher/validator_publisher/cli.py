import asyncio
import logging
import sys

from typing import List

import click
import yaml

from pragma_utils.logger import setup_logging

from validator_publisher import __version__
from validator_publisher.chain import PilotChain
from validator_publisher.config import SCHEMA_VERSION, ValidatorConfig
from validator_publisher.deployments import PILOT_PAIRS
from validator_publisher.preflight import (
    Check,
    blocking_failures,
    check_signer,
    check_staker,
    run_preflight,
)
from validator_publisher import runner

CONFIG_OPTION = click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    required=True,
    help="validator-publisher YAML config.",
)


def _load(config_file: str) -> ValidatorConfig:
    try:
        return ValidatorConfig.from_yaml(config_file)
    except Exception as e:
        raise click.ClickException(f"invalid config {config_file}: {e}")


def _print_checks(checks: List[Check]) -> None:
    for check in checks:
        mark = "ok  " if check.ok else ("FAIL" if check.blocking else "warn")
        click.echo(f"[{mark}] {check.name}: {check.detail}")


def _print_bind_instructions(
    config: ValidatorConfig, chain: PilotChain, signer: int
) -> None:
    bind = chain.bind_call(signer)
    click.echo(
        "\nThe staker must now confirm the oracle signer, from the staker wallet "
        "(this client never handles the staker key):\n"
        f"  contract:   {hex(bind.to_addr)}\n"
        "  entrypoint: bind_oracle_signer\n"
        f"  calldata:   [{hex(signer)}]\n"
        "\nWith starkli:\n"
        f"  starkli invoke {hex(bind.to_addr)} bind_oracle_signer {hex(signer)} "
        f"--account <staker-account.json> --keystore <staker-keystore.json> "
        f"--rpc {config.rpc_url}"
    )


async def _send(client, call) -> int:
    response = await client.account.execute_v3(calls=[call], auto_estimate=True)
    await client.full_node_client.wait_for_tx(response.transaction_hash)
    return response.transaction_hash


@click.group()
@click.version_option(__version__)
@click.option("--log-level", default="INFO", show_default=True)
def cli(log_level: str) -> None:
    """Pragma oracle publisher for Starknet validators."""
    setup_logging(logging.getLogger(), log_level)


@cli.command()
@click.option("-o", "--output", default="validator-publisher.yaml", show_default=True)
@click.option("--network", type=click.Choice(["mainnet", "sepolia"]), required=True)
@click.option("--rpc-url", required=True, help="JSON-RPC 0.10 URL of your node.")
@click.option("--staker-address", required=True)
@click.option("--oracle-signer-address", required=True)
@click.option(
    "--private-key",
    default="env:ORACLE_SIGNER_PRIVATE_KEY",
    show_default=True,
    help="Oracle signer key: env:VAR, keystore:PATH:PASSWORD, aws:SECRET or gcp:SECRET.",
)
def init(output, network, rpc_url, staker_address, oracle_signer_address, private_key):
    """Write a config file."""
    config = ValidatorConfig(
        schema_version=SCHEMA_VERSION,
        network=network,
        rpc_url=rpc_url,
        staker_address=staker_address,
        oracle_signer_address=oracle_signer_address,
        private_key=private_key,
    )
    data = config.model_dump(exclude={"contracts"})
    with open(output, "x") as file:
        yaml.safe_dump(data, file, sort_keys=False)
    click.echo(f"Wrote {output} (pairs: {', '.join(PILOT_PAIRS)})")


@cli.command()
@CONFIG_OPTION
@click.option("--skip-fetch", is_flag=True, help="Skip the dry-run fetch.")
def preflight(config_file: str, skip_fetch: bool):
    """Check the node, keys, registration and price sources."""
    config = _load(config_file)

    async def _run():
        chain = runner.build_chain(config)
        fetcher_client = (
            None if skip_fetch else await runner.build_fetcher_client(config)
        )
        return await run_preflight(config, chain, fetcher_client)

    checks = asyncio.run(_run())
    _print_checks(checks)
    if blocking_failures(checks):
        sys.exit(1)


@cli.command()
@CONFIG_OPTION
def register(config_file: str):
    """Declare the oracle signer, then print the call the staker signs."""
    config = _load(config_file)
    staker = int(config.staker_address, 16)
    signer = int(config.oracle_signer_address, 16)

    async def _run():
        chain = runner.build_chain(config)
        checks = await check_signer(config, chain) + await check_staker(config, chain)
        _print_checks(checks)
        if blocking_failures(checks):
            raise click.ClickException("fix the checks above before registering")
        if await chain.oracle_signer(staker) == signer:
            click.echo("Already registered.")
            return
        if await chain.declared_staker(signer) != staker:
            client = runner.build_onchain_client(config)
            tx = await _send(client, chain.declare_call(staker))
            click.echo(f"Declared the oracle signer for {hex(staker)} (tx {hex(tx)})")
        _print_bind_instructions(config, chain, signer)

    asyncio.run(_run())


@cli.command()
@CONFIG_OPTION
@click.option("--new-signer-address", required=True)
@click.option("--new-private-key", required=True, help="Same formats as private_key.")
def rotate(config_file: str, new_signer_address: str, new_private_key: str):
    """Declare a new oracle signer; the staker binds it, which releases the old one."""
    config = _load(config_file)
    rotated = config.model_copy(
        update={
            "oracle_signer_address": ValidatorConfig._address(new_signer_address),
            "private_key": ValidatorConfig._key(new_private_key),
        }
    )
    staker = int(config.staker_address, 16)
    signer = int(rotated.oracle_signer_address, 16)

    async def _run():
        chain = runner.build_chain(rotated)
        checks = await check_signer(rotated, chain) + await check_staker(rotated, chain)
        _print_checks(checks)
        if blocking_failures(checks):
            raise click.ClickException("fix the checks above before rotating")
        client = runner.build_onchain_client(rotated)
        tx = await _send(client, chain.declare_call(staker))
        click.echo(f"Declared {hex(signer)} for {hex(staker)} (tx {hex(tx)})")
        _print_bind_instructions(rotated, chain, signer)
        click.echo("\nThen update oracle_signer_address and private_key in the config.")

    asyncio.run(_run())


@cli.command()
@CONFIG_OPTION
@click.confirmation_option(
    prompt="Stop publishing for this staker until it binds a signer again?"
)
def revoke(config_file: str):
    """Emergency: the oracle signer revokes itself."""
    config = _load(config_file)

    async def _run():
        chain = runner.build_chain(config)
        client = runner.build_onchain_client(config)
        tx = await _send(client, chain.revoke_call(int(config.staker_address, 16)))
        click.echo(f"Revoked (tx {hex(tx)})")

    asyncio.run(_run())


@cli.command()
@CONFIG_OPTION
def status(config_file: str):
    """Registry status and oracle signer balance."""
    config = _load(config_file)

    async def _run():
        chain = runner.build_chain(config)
        staker = int(config.staker_address, 16)
        signer = int(config.oracle_signer_address, 16)
        click.echo(f"version:   {__version__}")
        click.echo(f"status:    {await chain.publisher_status(staker)}")
        click.echo(f"signer:    {hex(await chain.oracle_signer(staker))}")
        click.echo(f"balance:   {await chain.strk_balance(signer) / 10**18:.2f} STRK")
        click.echo(f"config:    {runner.config_hash(config)}")

    asyncio.run(_run())


@cli.command()
@CONFIG_OPTION
def run(config_file: str):
    """Publish prices until stopped."""
    asyncio.run(runner.run(_load(config_file)))


def main() -> None:
    cli()
