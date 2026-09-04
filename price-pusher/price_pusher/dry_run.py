"""
Run the real publisher pipeline without publishing, and check it.

    uv run python -m price_pusher.dry_run --config-file infra/price-pusher/config/config.mainnet.yaml

Builds every fetcher exactly as the price-pusher does for the given config,
fetches once, then:

  * asserts that no fetcher read a price from Pragma's own oracle (feedback
    loop, see pragma_sdk/common/fetchers/handlers/reference_price.py),
  * rejects zero prices,
  * compares every entry to the on-chain median of its pair and reports the
    ones further than --max-deviation.

Exit code is non-zero when the pipeline is not clean, so this can run in CI
or as a pre-deploy gate against a real network. This is the end-to-end check
of the publisher path; the unit tests only cover fetchers one by one.
"""

import asyncio
import collections
import statistics
import sys
import time

from typing import Dict, List, Optional
from unittest import mock

import click

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.utils import felt_to_str, str_to_felt
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.mixins.oracle import OracleMixin
from pragma_sdk.onchain.types import Network

from price_pusher.configs.price_config import PriceConfig
from price_pusher.core.fetchers import add_all_fetchers


class OracleReadError(AssertionError):
    """A fetcher tried to read a price from Pragma's oracle."""


async def _onchain_medians(
    client: PragmaOnChainClient, pairs: List[str]
) -> Dict[str, tuple]:
    out: Dict[str, tuple] = {}
    for pair in pairs:
        try:
            r = await OracleMixin.get_spot(client, str_to_felt(pair))
            out[pair] = (
                int(r.price) / 10 ** int(r.decimals),
                int(r.decimals),
                int(r.num_sources_aggregated),
            )
        except Exception:  # noqa: BLE001 - unregistered pair, no comparison
            out[pair] = (None, 8, 0)
    return out


async def run(
    config_file: str,
    network: Network,
    publisher_name: str,
    max_deviation: float,
    rpc_url: Optional[str],
) -> int:
    price_configs = PriceConfig.from_yaml(config_file)
    client = (
        PragmaOnChainClient(network=rpc_url, chain_name=network)
        if rpc_url
        else PragmaOnChainClient(network=network)
    )

    # Any fetcher reading our own median is a feedback loop: make it explode.
    with mock.patch.object(
        OracleMixin,
        "get_spot",
        side_effect=OracleReadError("a fetcher read a price from Pragma's oracle"),
    ) as oracle_reads:
        fetcher_client = await add_all_fetchers(
            FetcherClient(), publisher_name, price_configs
        )
        started = time.time()
        results = await fetcher_client.fetch(filter_exceptions=True)
        elapsed = time.time() - started

    entries = [r for r in results if isinstance(r, SpotEntry)]
    by_pair: Dict[str, List[SpotEntry]] = collections.defaultdict(list)
    for e in entries:
        by_pair[felt_to_str(e.pair_id)].append(e)

    medians = await _onchain_medians(client, sorted(by_pair))
    zero_prices = [e for e in entries if e.price <= 0]
    deviations = []
    for pair, es in sorted(by_pair.items()):
        onchain, decimals, _ = medians[pair]
        if not onchain:
            continue
        for e in es:
            dev = (e.price / 10**decimals - onchain) / onchain
            if abs(dev) > max_deviation:
                deviations.append((pair, felt_to_str(e.base.source), dev))

    click.echo(
        f"fetchers={len(fetcher_client.fetchers)} entries={len(entries)} "
        f"pairs={len(by_pair)} in {elapsed:.1f}s | oracle reads={oracle_reads.call_count} "
        f"| zero prices={len(zero_prices)}"
    )
    click.echo(
        f"{'pair':16}{'n':>3} {'local median':>14} {'on-chain':>14} {'dev':>8} {'srcs':>5}"
    )
    for pair, es in sorted(by_pair.items()):
        onchain, decimals, srcs = medians[pair]
        local = statistics.median(e.price / 10**decimals for e in es)
        dev = f"{(local - onchain) / onchain * 100:+.2f}%" if onchain else "n/a"
        click.echo(
            f"{pair:16}{len(es):3} {local:14.6g} {onchain or 0:14.6g} {dev:>8} {srcs:5}"
        )
    for pair, source, dev in deviations:
        click.echo(
            f"  DEVIATION {pair} {source} {dev * 100:+.1f}% off the on-chain median"
        )

    problems = []
    if oracle_reads.call_count:
        problems.append(f"{oracle_reads.call_count} oracle read(s) from fetchers")
    if zero_prices:
        problems.append(f"{len(zero_prices)} zero price(s)")
    if not entries:
        problems.append("no entries at all")
    if problems:
        click.echo("NOT CLEAN: " + "; ".join(problems), err=True)
        return 1
    click.echo(
        "clean"
        + (f" ({len(deviations)} deviation(s) to look at)" if deviations else "")
    )
    return 0


@click.command()
@click.option("--config-file", required=True, type=click.Path(exists=True))
@click.option("--network", default="mainnet", type=click.Choice(["mainnet", "sepolia"]))
@click.option("--publisher-name", default="DRY_RUN")
@click.option(
    "--max-deviation",
    default=0.03,
    show_default=True,
    help="Report entries beyond this fraction of the on-chain median.",
)
@click.option(
    "--rpc-url", default=None, help="Starknet RPC used for the on-chain comparison."
)
def cli(config_file, network, publisher_name, max_deviation, rpc_url):
    sys.exit(
        asyncio.run(run(config_file, network, publisher_name, max_deviation, rpc_url))
    )


if __name__ == "__main__":
    cli()
