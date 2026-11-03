import time

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from pragma_sdk.common.types.entry import SpotEntry
from pragma_sdk.common.utils import str_to_felt
from pragma_sdk.onchain.mixins.oracle import OracleMixin

from validator_publisher import preflight
from validator_publisher.chain import StakerInfo
from validator_publisher.config import ValidatorConfig

STAKER = 0x77D4B4E7AE321AABD0A5A7322108635FCBD0CD746F9AE217B8EA00363494B65
SIGNER = 0x5161
OPERATIONAL = 0x52DC40F04AD96BCE27C3EF4775037BF6EBD115C78CFD747F8DCD59E4AA24F2C
REWARD = 0x258DD1CAF7FFCBEDCEB0DFFD83EC17E31DF2888F19DDA09AC5C1C8505064DDE
SOURCES = ["BINANCE", "OKX", "BYBIT", "KUCOIN", "GATEIO"]


def _config(**overrides) -> ValidatorConfig:
    values = dict(
        schema_version=1,
        network="sepolia",
        rpc_url="http://pathfinder:9545/rpc/v0_10",
        staker_address=hex(STAKER),
        oracle_signer_address=hex(SIGNER),
        private_key="env:KEY",
        pairs=["BTC/USD"],
        contracts={"oracle": "0x111", "validator_registry": "0x222"},
    )
    values.update(overrides)
    return ValidatorConfig(**values)


class FakeChain:
    def __init__(self, **state):
        self.state = dict(
            chain_id="0x534e5f5345504f4c4941",  # SN_SEPOLIA
            spec="0.10.0",
            syncing=False,
            block_timestamp=int(time.time()),
            deployed=True,
            balance=100 * 10**18,
            staker=StakerInfo(REWARD, OPERATIONAL, None, 20_000 * 10**18),
            min_self_stake=20_000 * 10**18,
            status="ACTIVE",
            bound=SIGNER,
            declared=0,
            allowed=SOURCES,
        )
        self.state.update(state)
        s = self.state
        self.client = SimpleNamespace(
            get_chain_id=AsyncMock(return_value=s["chain_id"]),
            get_block=AsyncMock(
                return_value=SimpleNamespace(timestamp=s["block_timestamp"])
            ),
        )

    async def rpc(self, method):
        return {
            "starknet_specVersion": self.state["spec"],
            "starknet_syncing": self.state["syncing"],
        }[method]

    async def is_deployed(self, address):
        return self.state["deployed"]

    async def strk_balance(self, account):
        return self.state["balance"]

    async def staker_info(self, staker):
        return self.state["staker"]

    async def min_self_stake(self):
        return self.state["min_self_stake"]

    async def publisher_status(self, staker):
        return self.state["status"]

    async def oracle_signer(self, staker):
        return self.state["bound"]

    async def declared_staker(self, signer):
        return self.state["declared"]

    async def allowed_sources(self):
        return [str_to_felt(s) for s in self.state["allowed"]]


def _failed(checks):
    return {c.name: c.detail for c in checks if not c.ok}


@pytest.mark.asyncio
async def test_healthy_setup_passes():
    checks = await preflight.run_preflight(_config(), FakeChain())
    assert _failed(checks) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state, name",
    [
        ({"chain_id": "0x534e5f4d41494e"}, "chain id"),
        ({"spec": "0.9.0"}, "rpc version"),
        ({"syncing": {"current_block_num": 1, "highest_block_num": 100}}, "node sync"),
        ({"block_timestamp": int(time.time()) - 600}, "clock"),
        ({"balance": 10**18}, "signer balance"),
        ({"min_self_stake": 30_000 * 10**18}, "self stake"),
    ],
)
async def test_each_check_catches_its_failure(state, name):
    checks = await preflight.run_preflight(_config(), FakeChain(**state))
    assert name in _failed(checks)


@pytest.mark.asyncio
async def test_undeployed_signer_fails():
    checks = await preflight.check_signer(_config(), FakeChain(deployed=False))
    assert "no account deployed" in _failed(checks)["oracle signer"]


@pytest.mark.asyncio
async def test_operational_key_reuse_fails():
    checks = await preflight.check_staker(
        _config(oracle_signer_address=hex(OPERATIONAL)), FakeChain()
    )
    assert "operational address" in _failed(checks)["key separation"]


@pytest.mark.asyncio
async def test_exiting_staker_fails():
    chain = FakeChain(
        staker=StakerInfo(REWARD, OPERATIONAL, 1_800_000_000, 20_000 * 10**18)
    )
    checks = await preflight.check_staker(_config(), chain)
    assert "unstake intent" in _failed(checks)["staker"]


@pytest.mark.asyncio
async def test_not_a_staker_fails():
    checks = await preflight.check_staker(_config(), FakeChain(staker=None))
    assert "is not a staker" in _failed(checks)["staker"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state, detail",
    [
        ({"status": "NOT_BOUND", "bound": 0}, "run `pragma-validator register`"),
        (
            {"status": "NOT_BOUND", "bound": 0, "declared": STAKER},
            "waiting for the staker",
        ),
        ({"status": "ACTIVE", "bound": 0x999}, "another signer"),
        ({"status": "EXITING"}, "status EXITING"),
    ],
)
async def test_registration_states(state, detail):
    checks = await preflight.check_registration(_config(), FakeChain(**state))
    assert detail in _failed(checks)["registration"]


def _fetcher(entries, oracle_read=False):
    async def fetch(filter_exceptions=True):
        if oracle_read:
            try:
                await OracleMixin.get_spot(None, 0)
            except AssertionError:
                pass
        return entries

    return SimpleNamespace(fetch=fetch)


def _entries(sources, price=80_000 * 10**8):
    return [SpotEntry("BTC/USD", price, 1, source, hex(STAKER)) for source in sources]


@pytest.mark.asyncio
async def test_fetch_quorum_and_reference_pass():
    with patch.object(
        preflight,
        "get_reference_price_provider",
        return_value=SimpleNamespace(get_price=AsyncMock(return_value=80_100.0)),
    ):
        checks = await preflight.check_fetch(
            _config(), FakeChain(), _fetcher(_entries(SOURCES))
        )
    assert _failed(checks) == {}


@pytest.mark.asyncio
async def test_fewer_than_four_allowed_sources_fails():
    with patch.object(
        preflight,
        "get_reference_price_provider",
        return_value=SimpleNamespace(get_price=AsyncMock(return_value=80_000.0)),
    ):
        checks = await preflight.check_fetch(
            _config(), FakeChain(allowed=SOURCES[:3]), _fetcher(_entries(SOURCES))
        )
    failed = _failed(checks)
    assert "3 allowed source(s)" in failed["BTC/USD sources"]
    whitelist = next(c for c in checks if c.name == "BTC/USD whitelist")
    assert not whitelist.blocking


@pytest.mark.asyncio
async def test_oracle_read_by_a_fetcher_fails():
    with patch.object(
        preflight,
        "get_reference_price_provider",
        return_value=SimpleNamespace(get_price=AsyncMock(return_value=80_000.0)),
    ):
        checks = await preflight.check_fetch(
            _config(), FakeChain(), _fetcher(_entries(SOURCES), oracle_read=True)
        )
    assert "feedback loop" in _failed(checks)


@pytest.mark.asyncio
async def test_price_far_from_independent_reference_fails():
    with patch.object(
        preflight,
        "get_reference_price_provider",
        return_value=SimpleNamespace(get_price=AsyncMock(return_value=40_000.0)),
    ):
        checks = await preflight.check_fetch(
            _config(), FakeChain(), _fetcher(_entries(SOURCES))
        )
    assert "from independent venues" in _failed(checks)["BTC/USD reference"]
