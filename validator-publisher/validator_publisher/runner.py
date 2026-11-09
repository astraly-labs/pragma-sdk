"""
The price-pusher pipeline, set up for a validator: its own node for every
chain read and write, its own entries to decide when to push, the pilot
contracts, and the staker address as publisher id.
"""

import asyncio
import hashlib
import logging

from typing import Optional

from prometheus_client import Gauge, Info

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.interface import set_shared_client
from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.types.execution_config import ExecutionConfig
from pragma_utils.cli import load_private_key_from_cli_arg

from price_pusher.core.fetchers import add_all_fetchers
from price_pusher.core.listener import PriceListener
from price_pusher.core.poller import PricePoller
from price_pusher.core.pusher import PricePusher
from price_pusher.core.request_handlers.publisher import PublisherRequestHandler
from price_pusher.fastapi_health_server import FastAPIHealthServer
from price_pusher.main import (
    _create_health_server,
    _default_max_seconds_without_push,
    _install_signal_handlers,
)

from validator_publisher import __version__
from validator_publisher.chain import PilotChain
from validator_publisher.config import ValidatorConfig
from validator_publisher.source_coverage import CoverageOrchestrator

logger = logging.getLogger(__name__)

LISTENER_POLLING_S = 20
POLLER_REFRESH_S = 5
STATUS_REFRESH_S = 60
MAX_SECONDS_WITHOUT_POLL = 300


def build_onchain_client(config: ValidatorConfig) -> PragmaOnChainClient:
    return PragmaOnChainClient(
        network=config.rpc_url,
        chain_name=config.network,
        account_contract_address=config.oracle_signer_address,
        account_private_key=load_private_key_from_cli_arg(config.private_key),
        contract_addresses_config=config.deployment().contract_addresses(),
        execution_config=ExecutionConfig(auto_estimate=True),
    )


def build_chain(config: ValidatorConfig) -> PilotChain:
    deployment = config.deployment()
    return PilotChain(
        config.rpc_url,
        config.network,
        registry=deployment.validator_registry,
        oracle=deployment.oracle,
    )


async def build_fetcher_client(config: ValidatorConfig) -> FetcherClient:
    if config.network == "mainnet":
        # on-chain fetchers (Ekubo) read mainnet through the validator's node
        set_shared_client(
            "mainnet", PragmaOnChainClient(network=config.rpc_url, chain_name="mainnet")
        )
    return await add_all_fetchers(
        fetcher_client=FetcherClient(),
        publisher_name=config.staker_address,
        price_configs=[config.price_config()],
        evm_rpc_urls=config.evm_rpc_urls or None,
    )


class ValidatorMetrics:
    def __init__(
        self, health_server: Optional[FastAPIHealthServer], config: ValidatorConfig
    ):
        registry = health_server.metrics.registry if health_server else None
        self.enabled = registry is not None
        if not self.enabled:
            return
        build = Info(
            "validator_publisher_build",
            "Release and config of this publisher",
            registry=registry,
        )
        build.info({"version": __version__, "config_hash": config_hash(config)})
        self.status = Gauge(
            "validator_publisher_registry_status",
            "1 for the current ValidatorRegistry status of this publisher",
            ["status"],
            registry=registry,
        )
        self.balance = Gauge(
            "validator_publisher_signer_balance_strk",
            "STRK left on the oracle signer account",
            registry=registry,
        )
        self.pair_sources = Gauge(
            "validator_publisher_pair_sources",
            "Allowed sources that answered in the last poll for this pair",
            ["pair"],
            registry=registry,
        )

    def record_sources(self, pair: str, count: int) -> None:
        if self.enabled:
            self.pair_sources.labels(pair=pair).set(count)

    async def refresh_forever(self, config: ValidatorConfig, chain: PilotChain) -> None:
        if not self.enabled:
            return
        staker = int(config.staker_address, 16)
        signer = int(config.oracle_signer_address, 16)
        while True:
            try:
                status = await chain.publisher_status(staker)
                self.status.clear()
                self.status.labels(status=status).set(1)
                self.balance.set(await chain.strk_balance(signer) / 10**18)
            except Exception as e:
                logger.warning(f"Could not refresh the registry status: {e}")
            await asyncio.sleep(STATUS_REFRESH_S)


def config_hash(config: ValidatorConfig) -> str:
    """Identifies operators running the same settings, secrets excluded."""
    public = config.model_dump(exclude={"private_key", "rpc_url", "evm_rpc_urls"})
    return hashlib.sha256(repr(sorted(public.items())).encode()).hexdigest()[:12]


async def run(config: ValidatorConfig) -> None:
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    price_config = config.price_config()
    health_server = _create_health_server(
        health_port=config.health_port,
        health_server_type="fastapi",
        max_seconds_without_push=_default_max_seconds_without_push([price_config]),
        max_seconds_without_poll=MAX_SECONDS_WITHOUT_POLL,
    )
    if health_server:
        await health_server.start()

    try:
        client = build_onchain_client(config)
        chain = build_chain(config)
        metrics = ValidatorMetrics(health_server, config)
        fetcher_client = await build_fetcher_client(config)
        allowed_sources = set(await chain.allowed_sources())
        if stop.is_set():
            return

        pusher = PricePusher(
            client=client,
            on_successful_push=health_server.update_last_push
            if health_server
            else None,
            publisher_name=config.staker_address,
            rpc_urls=[config.rpc_url],
        )
        listener = PriceListener(
            request_handler=PublisherRequestHandler(client, config.staker_address),
            price_config=price_config,
            polling_frequency_in_s=LISTENER_POLLING_S,
        )
        orchestrator = CoverageOrchestrator(
            pairs=config.pairs,
            allowed_sources=allowed_sources,
            on_coverage=metrics.record_sources,
            poller=PricePoller(fetcher_client=fetcher_client),
            listeners=[listener],
            pusher=pusher,
            poller_refresh_interval=POLLER_REFRESH_S,
            health=health_server.status if health_server else None,
            stop_event=stop,
        )
        background = [
            asyncio.create_task(metrics.refresh_forever(config, chain)),
            asyncio.create_task(orchestrator.refresh_allowed_sources_forever(chain)),
        ]
        try:
            logger.info(
                f"🚀 validator-publisher {__version__} publishing for {config.staker_address}"
            )
            await orchestrator.run_forever()
        finally:
            for task in background:
                task.cancel()
    finally:
        if health_server:
            await health_server.stop()
