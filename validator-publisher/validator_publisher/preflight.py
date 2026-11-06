"""
Checks run before publishing, and by `pragma-validator preflight`. A failure
means the publisher would not publish, or would publish something wrong.
"""

import collections
import statistics
import time

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from unittest import mock

from pragma_sdk.common.fetchers.fetcher_client import FetcherClient
from pragma_sdk.common.fetchers.handlers.reference_price import (
    get_reference_price_provider,
)
from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.types.pair import Pair
from pragma_sdk.common.utils import felt_to_str
from pragma_sdk.onchain.constants import CHAIN_IDS
from pragma_sdk.onchain.mixins.oracle import OracleMixin

from validator_publisher.chain import PilotChain
from validator_publisher.config import ValidatorConfig
from validator_publisher.quorum import MIN_SOURCES_PER_PAIR

MAX_SYNC_LAG_BLOCKS = 10
MAX_CLOCK_SKEW_S = 30
MAX_REFERENCE_DEVIATION = 0.02
STATUS_ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    blocking: bool = True


def _ok(name: str, detail: str) -> Check:
    return Check(name, True, detail)


def _fail(name: str, detail: str, blocking: bool = True) -> Check:
    return Check(name, False, detail, blocking)


async def check_node(config: ValidatorConfig, chain: PilotChain) -> List[Check]:
    checks = []
    chain_id = int(await chain.client.get_chain_id(), 16)
    expected = CHAIN_IDS[config.network].value
    checks.append(
        _ok("chain id", config.network)
        if chain_id == expected
        else _fail(
            "chain id", f"node is on {hex(chain_id)}, config says {config.network}"
        )
    )

    spec = str(await chain.rpc("starknet_specVersion"))
    checks.append(
        _ok("rpc version", spec)
        if spec.startswith("0.10")
        else _fail("rpc version", f"{spec}, the publisher needs JSON-RPC 0.10")
    )

    syncing = await chain.rpc("starknet_syncing")
    if not syncing:
        checks.append(_ok("node sync", "synced"))
    else:
        lag = int(syncing["highest_block_num"]) - int(syncing["current_block_num"])
        checks.append(
            _ok("node sync", f"{lag} block(s) behind")
            if lag <= MAX_SYNC_LAG_BLOCKS
            else _fail("node sync", f"{lag} blocks behind the network head")
        )

    block = await chain.client.get_block(block_number="latest")
    skew = abs(time.time() - block.timestamp)
    checks.append(
        _ok("clock", f"{skew:.0f}s from the latest block")
        if skew <= MAX_CLOCK_SKEW_S
        else _fail("clock", f"{skew:.0f}s from the latest block, fix NTP")
    )
    return checks


async def check_signer(config: ValidatorConfig, chain: PilotChain) -> List[Check]:
    signer = int(config.oracle_signer_address, 16)
    if not await chain.is_deployed(signer):
        return [_fail("oracle signer", f"no account deployed at {hex(signer)}")]
    balance = await chain.strk_balance(signer) / 10**18
    return [
        _ok("oracle signer", "account deployed"),
        _ok("signer balance", f"{balance:.2f} STRK")
        if balance >= config.min_signer_balance_strk
        else _fail(
            "signer balance",
            f"{balance:.2f} STRK, below {config.min_signer_balance_strk} STRK",
        ),
    ]


async def check_staker(config: ValidatorConfig, chain: PilotChain) -> List[Check]:
    staker = int(config.staker_address, 16)
    signer = int(config.oracle_signer_address, 16)
    info = await chain.staker_info(staker)
    if info is None:
        return [_fail("staker", f"{hex(staker)} is not a staker")]
    checks = [
        _ok("staker", "registered in staking")
        if info.unstake_time is None
        else _fail(
            "staker", "unstake intent sent, the registry revokes exiting stakers"
        )
    ]
    reused = {
        "operational address": info.operational_address,
        "reward address": info.reward_address,
    }
    clashes = [name for name, address in reused.items() if address == signer]
    checks.append(
        _fail("key separation", f"oracle signer is the {', '.join(clashes)}")
        if clashes
        else _ok("key separation", "oracle signer is a dedicated account")
    )
    minimum = await chain.min_self_stake()
    checks.append(
        _ok("self stake", f"{info.amount_own / 10**18:,.0f} STRK")
        if info.amount_own >= minimum
        else _fail(
            "self stake",
            f"{info.amount_own / 10**18:,.0f} STRK, the pilot requires {minimum / 10**18:,.0f}",
        )
    )
    return checks


async def check_registration(config: ValidatorConfig, chain: PilotChain) -> List[Check]:
    staker = int(config.staker_address, 16)
    signer = int(config.oracle_signer_address, 16)
    status = await chain.publisher_status(staker)
    bound = await chain.oracle_signer(staker)
    if status == STATUS_ACTIVE and bound == signer:
        return [_ok("registration", "active")]
    if bound not in (0, signer):
        return [
            _fail("registration", f"staker is bound to another signer {hex(bound)}")
        ]
    if bound == 0:
        if await chain.declared_staker(signer) == staker:
            return [_fail("registration", "declared, waiting for the staker's bind")]
        return [
            _fail("registration", "not registered, run `pragma-validator register`")
        ]
    return [_fail("registration", f"status {status}")]


async def check_fetch(
    config: ValidatorConfig, chain: PilotChain, fetcher_client: FetcherClient
) -> List[Check]:
    """
    One fetch through the real fetchers, Pragma's oracle reads blocked: any
    read is a feedback loop. Then the source quorum and an independent check.
    """
    with mock.patch.object(
        OracleMixin, "get_spot", side_effect=AssertionError("oracle read")
    ) as oracle_reads:
        results = await fetcher_client.fetch(filter_exceptions=True)

    entries = [r for r in results if isinstance(r, SpotEntry) and r.price > 0]
    by_pair: Dict[str, List[SpotEntry]] = collections.defaultdict(list)
    for entry in entries:
        by_pair[felt_to_str(entry.pair_id)].append(entry)

    checks = [
        _ok("feedback loop", "no fetcher reads Pragma's oracle")
        if oracle_reads.call_count == 0
        else _fail("feedback loop", f"{oracle_reads.call_count} oracle read(s)")
    ]

    allowed: Set[int] = set(await chain.allowed_sources())
    for pair in config.pairs:
        found = by_pair.get(pair, [])
        usable = {e.base.source for e in found if e.base.source in allowed}
        checks.append(
            _ok(f"{pair} sources", f"{len(usable)} allowed source(s)")
            if len(usable) >= MIN_SOURCES_PER_PAIR
            else _fail(
                f"{pair} sources",
                f"{len(usable)} allowed source(s), {MIN_SOURCES_PER_PAIR} required",
            )
        )
        dropped = sorted(
            {felt_to_str(e.base.source) for e in found}
            - {felt_to_str(s) for s in usable}
        )
        if dropped:
            checks.append(
                _fail(
                    f"{pair} whitelist",
                    f"not allowed by the registry, will not be published: {', '.join(dropped)}",
                    blocking=False,
                )
            )
        if found:
            checks.append(await _reference_check(pair, found))
    return checks


async def _reference_check(pair: str, entries: List[SpotEntry]) -> Check:
    name = f"{pair} reference"
    base, quote = pair.split("/")
    decimals = Pair.from_tickers(base, quote).decimals()
    local = statistics.median(e.price for e in entries) / 10**decimals
    try:
        reference = await get_reference_price_provider().get_price(base, quote)
    except Exception as e:
        return _fail(name, f"independent reference unavailable: {e}", blocking=False)
    deviation = (local - reference) / reference
    if abs(deviation) <= MAX_REFERENCE_DEVIATION:
        return _ok(name, f"{deviation * 100:+.2f}% from independent venues")
    return _fail(name, f"{deviation * 100:+.2f}% from independent venues")


def blocking_failures(checks: List[Check]) -> List[Check]:
    return [c for c in checks if not c.ok and c.blocking]


async def run_preflight(
    config: ValidatorConfig,
    chain: PilotChain,
    fetcher_client: Optional[FetcherClient] = None,
) -> List[Check]:
    checks = await check_node(config, chain)
    checks += await check_signer(config, chain)
    checks += await check_staker(config, chain)
    checks += await check_registration(config, chain)
    if fetcher_client is not None:
        checks += await check_fetch(config, chain, fetcher_client)
    return checks
