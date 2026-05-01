import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from starknet_py.net.client_errors import ClientError

from pragma_sdk.onchain.client import PragmaOnChainClient
from pragma_sdk.onchain.rpc_monitor import (
    RPCHealthMonitor,
    RPC_HEALTH_CHECK_INTERVAL,
    MAX_RPC_FAILURES,
)
from pragma_sdk.onchain.constants import RPC_URLS

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_client():
    client = MagicMock(spec=PragmaOnChainClient)
    client.network = "mainnet"
    client.full_node_client = AsyncMock()
    client.full_node_client.url = RPC_URLS["mainnet"][0]
    client._create_full_node_client = MagicMock()
    return client


@pytest.fixture
def rpc_monitor(mock_client):
    return RPCHealthMonitor(mock_client)


@pytest.mark.asyncio
async def test_check_rpc_health_success(rpc_monitor, mock_client):
    """Test RPC health check when RPC is healthy"""
    mock_client.full_node_client.get_block_number = AsyncMock(return_value=100)
    assert await rpc_monitor.check_rpc_health() is True


@pytest.mark.asyncio
async def test_check_rpc_health_failure(rpc_monitor, mock_client):
    """Test RPC health check when RPC fails"""
    mock_client.full_node_client.get_block_number = AsyncMock(
        side_effect=ClientError("RPC Error")
    )
    assert await rpc_monitor.check_rpc_health() is False


@pytest.mark.asyncio
async def test_switch_rpc_success(rpc_monitor, mock_client):
    """Test successful RPC switch to a new RPC"""
    current_rpc = mock_client.full_node_client.url
    mock_client._create_full_node_client.return_value = AsyncMock()

    success = await rpc_monitor.switch_rpc()
    assert success is True

    # Verify we switched to a different RPC
    new_rpc = mock_client.full_node_client.url
    assert new_rpc != current_rpc
    assert current_rpc in rpc_monitor.failed_rpcs


@pytest.mark.asyncio
async def test_switch_rpc_all_failed(rpc_monitor, mock_client):
    """Test RPC switching behavior when all RPCs have failed"""
    # Mark all RPCs as failed
    rpc_monitor.failed_rpcs.update(RPC_URLS["mainnet"])

    # Create a new mock client with URL property
    new_mock_client = AsyncMock()
    new_mock_client.url = mock_client.full_node_client.url
    mock_client._create_full_node_client.return_value = new_mock_client

    success = await rpc_monitor.switch_rpc()
    assert success is True

    # Verify failed RPCs were cleared except for the current one
    assert len(rpc_monitor.failed_rpcs) == 1  # Only contains the current RPC
    assert mock_client.full_node_client.url in rpc_monitor.failed_rpcs


@pytest.mark.asyncio
async def test_monitor_rpc_health_switches_on_failure(rpc_monitor, mock_client):
    """Test that health monitor switches RPC after MAX_RPC_FAILURES"""
    # Setup the initial RPC to always fail
    mock_client.full_node_client.get_block_number = AsyncMock(
        side_effect=ClientError("RPC Error")
    )

    # Create a new mock client that will return healthy results once switched
    new_mock_client = AsyncMock()
    new_mock_client.url = "https://new-mock-rpc.io"
    new_mock_client.get_block_number = AsyncMock(return_value=100)
    mock_client._create_full_node_client.return_value = new_mock_client

    # Patch asyncio.sleep with a fast sleep that yields immediately
    original_sleep = asyncio.sleep

    async def fast_sleep(duration):
        await original_sleep(0)

    with patch("asyncio.sleep", fast_sleep):
        monitor_task = asyncio.create_task(rpc_monitor.monitor_rpc_health())
        await original_sleep(0.1)
        monitor_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await monitor_task

    # Verify the switch occurred:
    assert mock_client.full_node_client.url == new_mock_client.url
    # Failures should be reset after switching
    assert rpc_monitor.current_rpc_failures < MAX_RPC_FAILURES


@pytest.mark.asyncio
async def test_no_duplicate_rpc_selection(rpc_monitor, mock_client):
    """Test that we don't select the same RPC twice in a row"""
    initial_rpc = mock_client.full_node_client.url
    used_rpcs = {initial_rpc}

    # Try switching multiple times
    for i in range(3):
        # Ensure each new client has a unique URL
        new_mock_client = AsyncMock()
        new_mock_client.url = f"https://new-mock-rpc-{i}.io"
        mock_client._create_full_node_client.return_value = new_mock_client

        await rpc_monitor.switch_rpc()
        new_rpc = mock_client.full_node_client.url
        # Verify we got a different RPC
        assert new_rpc not in used_rpcs
        used_rpcs.add(new_rpc)


@pytest.mark.asyncio
async def test_failure_count_reset_after_switch(rpc_monitor, mock_client):
    """Test that failure count resets after successful RPC switch"""
    rpc_monitor.current_rpc_failures = MAX_RPC_FAILURES
    mock_client._create_full_node_client.return_value = AsyncMock()

    await rpc_monitor.switch_rpc()
    assert rpc_monitor.current_rpc_failures == 0


@pytest.mark.asyncio
async def test_continuous_retry_on_all_failures(rpc_monitor, mock_client):
    """Test that monitor keeps retrying even when all RPCs have failed"""
    # Setup the initial RPC to always fail
    mock_client.full_node_client.get_block_number = AsyncMock(
        side_effect=ClientError("RPC Error")
    )

    # Create a new mock client that also fails
    new_mock_client = AsyncMock()
    new_mock_client.url = "https://new-mock-rpc.io"
    new_mock_client.get_block_number = AsyncMock(side_effect=ClientError("RPC Error"))
    mock_client._create_full_node_client.return_value = new_mock_client

    attempts = 0
    original_sleep = asyncio.sleep

    async def counting_sleep(duration):
        nonlocal attempts
        attempts += 1
        await original_sleep(0)

    with patch("asyncio.sleep", counting_sleep):
        monitor_task = asyncio.create_task(rpc_monitor.monitor_rpc_health())
        await original_sleep(0.1)
        monitor_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await monitor_task

    # Ensure we had several iterations (attempts)
    assert attempts >= 3
    assert len(rpc_monitor.failed_rpcs) > 0


@pytest.mark.asyncio
async def test_health_check_interval_respected(rpc_monitor):
    """Test that health check interval is respected"""
    original_sleep = asyncio.sleep
    recorded_calls = []

    async def fake_sleep(duration):
        recorded_calls.append(duration)
        await original_sleep(0)

    # Patch asyncio.sleep with our custom function.
    with patch("asyncio.sleep", side_effect=fake_sleep):
        monitor_task = asyncio.create_task(rpc_monitor.monitor_rpc_health())
        # Allow one iteration of the loop to occur.
        await original_sleep(0.1)
        monitor_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await monitor_task

        # Filter out any calls made by the test itself (e.g. 0.1)
        monitor_calls = [d for d in recorded_calls if d == RPC_HEALTH_CHECK_INTERVAL]
        assert monitor_calls, f"Expected a sleep call with {RPC_HEALTH_CHECK_INTERVAL}, got {recorded_calls}"


@pytest.mark.asyncio
async def test_error_handling_in_monitor(rpc_monitor, mock_client):
    """Test error handling in the monitor loop"""
    # Force an unexpected error in the health check
    mock_client.full_node_client.get_block_number = AsyncMock(
        side_effect=Exception("Unexpected error")
    )
    original_sleep = asyncio.sleep

    async def fast_sleep(duration):
        await original_sleep(0)

    with patch("asyncio.sleep", fast_sleep):
        monitor_task = asyncio.create_task(rpc_monitor.monitor_rpc_health())
        await original_sleep(0.1)
        monitor_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await monitor_task
    # If we reach here without crashing, error handling works as expected.
    assert True
