"""
Liveness is progress of the poll loop; readiness is a recent push. A publisher
that has nothing to push (fresh entries on-chain, no deviation) must stay
live: killing it for that is the 12-minute restart loop of September 2026.
"""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from price_pusher.fastapi_health_server import FastAPIHealthServer
from price_pusher.health import HealthStatus
from price_pusher.health_server import HealthServer
from price_pusher.orchestrator import Orchestrator


def test_starting_is_live_but_not_ready():
    status = HealthStatus(startup_time=1000.0)
    code, body = status.liveness(now=1240.0)
    assert (code, body["state"]) == (200, "starting")
    code, body = status.readiness(now=1240.0)
    assert (code, body["state"]) == (503, "warming_up")


def test_polling_without_pushing_stays_live():
    status = HealthStatus(max_seconds_without_push=300, startup_time=1000.0)
    status.orchestration_started_at = 1010.0
    status.last_poll_timestamp = 5000.0
    status.last_push_timestamp = 1100.0  # 65 minutes ago: nothing to push
    code, body = status.liveness(now=5005.0)
    assert (code, body["state"]) == (200, "active")
    code, body = status.readiness(now=5005.0)
    assert (code, body["state"]) == (503, "stale")


def test_stalled_poll_loop_is_not_live():
    status = HealthStatus(max_seconds_without_poll=300)
    status.orchestration_started_at = 1000.0
    status.last_poll_timestamp = 1000.0
    status.last_push_timestamp = 1290.0  # a push does not prove the loop is alive
    code, body = status.liveness(now=1301.0)
    assert (code, body["state"]) == (503, "stalled")


def test_orchestration_start_counts_as_progress_until_the_first_poll():
    status = HealthStatus(max_seconds_without_poll=300)
    status.orchestration_started_at = 1000.0
    assert status.liveness(now=1200.0)[0] == 200
    assert status.liveness(now=1301.0)[0] == 503


async def _get(port: int, path: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://127.0.0.1:{port}{path}") as resp:
            return resp.status, await resp.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("server_cls", [FastAPIHealthServer, HealthServer])
async def test_server_answers_before_orchestration_and_stops_cleanly(server_cls):
    server = server_cls(port=0)
    await server.start()
    port = _bound_port(server)
    try:
        code, body = await _get(port, "/health")
        assert (code, body["state"]) == (200, "starting")
        code, body = await _get(port, "/ready")
        assert (code, body["state"]) == (503, "warming_up")

        server.status.orchestration_started()
        server.status.record_poll()
        server.update_last_push()
        code, body = await _get(port, "/health")
        assert (code, body["state"], body["total_pushes"]) == (200, "active", 1)
        assert (await _get(port, "/ready"))[0] == 200
    finally:
        await server.stop()

    with pytest.raises(aiohttp.ClientConnectorError):
        await _get(port, "/health")


def _bound_port(server) -> int:
    if isinstance(server, FastAPIHealthServer):
        return server._server.servers[0].sockets[0].getsockname()[1]
    return server._runner.addresses[0][1]


def _orchestrator(miden_client=None, **kwargs) -> Orchestrator:
    poller = MagicMock()
    poller.poll_prices = AsyncMock()
    pusher = MagicMock()
    pusher.miden_client = miden_client
    return Orchestrator(
        poller=poller,
        listeners=[],
        pusher=pusher,
        poller_refresh_interval=1,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_run_forever_returns_on_stop_and_records_polls():
    health = HealthStatus()
    orchestrator = _orchestrator(health=health)
    task = asyncio.create_task(orchestrator.run_forever())
    await asyncio.sleep(0.1)
    assert health.orchestration_started_at is not None
    assert health.last_poll_timestamp is not None

    orchestrator.request_stop()
    await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_stop_lets_the_running_miden_tick_finish():
    tick = {"started": 0, "finished": 0}

    async def publish_to_miden(entries):
        tick["started"] += 1
        await asyncio.sleep(0.3)  # a pm_publisher call in its worker thread
        tick["finished"] += 1

    miden_client = MagicMock()
    miden_client.maintain_fee_balance = AsyncMock()
    orchestrator = _orchestrator(miden_client=miden_client, miden_publish_interval=60)
    orchestrator.pusher.publish_to_miden = publish_to_miden
    orchestrator.last_polled_entries = ["entry"]

    task = asyncio.create_task(orchestrator.run_forever())
    await asyncio.sleep(0.1)
    assert tick == {"started": 1, "finished": 0}
    orchestrator.request_stop()
    await asyncio.wait_for(task, timeout=2)
    assert tick == {"started": 1, "finished": 1}


@pytest.mark.asyncio
async def test_stop_cancels_a_miden_tick_that_overruns_the_grace_period():
    async def publish_to_miden(entries):
        await asyncio.sleep(60)

    miden_client = MagicMock()
    orchestrator = _orchestrator(
        miden_client=miden_client, miden_publish_interval=60, miden_shutdown_timeout=0.2
    )
    orchestrator.pusher.publish_to_miden = publish_to_miden
    orchestrator.last_polled_entries = ["entry"]

    task = asyncio.create_task(orchestrator.run_forever())
    await asyncio.sleep(0.1)
    orchestrator.request_stop()
    await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_a_crashed_service_takes_the_orchestration_down():
    orchestrator = _orchestrator()
    orchestrator.poller.poll_prices = AsyncMock(side_effect=RuntimeError("poller died"))
    with pytest.raises(RuntimeError, match="poller died"):
        await asyncio.wait_for(orchestrator.run_forever(), timeout=2)


@pytest.mark.asyncio
async def test_sigterm_sets_the_stop_event():
    from price_pusher.main import _install_signal_handlers

    stop = asyncio.Event()
    _install_signal_handlers(stop)
    try:
        signal.raise_signal(signal.SIGTERM)
        await asyncio.wait_for(stop.wait(), timeout=2)
    finally:
        loop = asyncio.get_running_loop()
        loop.remove_signal_handler(signal.SIGTERM)
        loop.remove_signal_handler(signal.SIGINT)
