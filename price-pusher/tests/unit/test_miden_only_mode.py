import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from price_pusher import main as pusher_main
from price_pusher.core.poller import PricePoller
from price_pusher.core.pusher import PricePusher
from price_pusher.orchestrator import Orchestrator

CONFIG = """
- pairs:
    spot:
      - BTC/USD
  time_difference: 1800
  price_deviation: 0.01
  miden_only: true
"""


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG)
    return str(path)


def run_cli(config_file, *args):
    with (
        patch.object(pusher_main, "main", MagicMock(return_value=None)) as main_mock,
        patch.object(pusher_main.asyncio, "run"),
    ):
        result = CliRunner().invoke(
            pusher_main.cli_entrypoint,
            ["-c", config_file, "--publisher-name", "pragma", *args],
        )
    return result, main_mock


def test_miden_only_needs_no_starknet_option(config_file):
    result, main_mock = run_cli(
        config_file, "--miden-only", "--miden-network", "testnet"
    )
    assert result.exit_code == 0, result.output
    kwargs = main_mock.call_args.kwargs
    assert kwargs["miden_only"] is True
    assert kwargs["private_key"] is None
    assert kwargs["network"] is None


def test_miden_only_needs_a_miden_network(config_file):
    result, _ = run_cli(config_file, "--miden-only")
    assert result.exit_code != 0
    assert "--miden-network" in result.output


@pytest.mark.parametrize(
    "given,missing",
    [
        (["-p", "plain:0x1", "--publisher-address", "0x1"], "--network"),
        (["-n", "sepolia", "--publisher-address", "0x1"], "--private-key"),
        (["-n", "sepolia", "-p", "plain:0x1"], "--publisher-address"),
    ],
)
def test_starknet_options_stay_required_without_miden_only(
    config_file, given, missing
):
    result, _ = run_cli(config_file, *given)
    assert result.exit_code != 0
    assert missing in result.output


@pytest.mark.asyncio
async def test_orchestration_without_listeners_keeps_running_until_stopped():
    poller = AsyncMock(spec=PricePoller)
    pusher = AsyncMock(spec=PricePusher)
    pusher.miden_client = None
    orchestrator = Orchestrator(poller=poller, listeners=[], pusher=pusher)

    task = asyncio.create_task(orchestrator.run_forever())
    await asyncio.sleep(0.3)
    assert not task.done(), "a Miden-only orchestration must not stop by itself"

    orchestrator.request_stop()
    await asyncio.wait_for(task, timeout=5)
