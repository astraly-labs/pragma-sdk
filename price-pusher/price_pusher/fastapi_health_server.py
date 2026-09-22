import asyncio
import contextlib
import logging
import time

from typing import Iterator, Optional

import uvicorn

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from price_pusher.health import HealthStatus
from price_pusher.metrics import PrometheusMetrics

logger = logging.getLogger(__name__)


class _Server(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        # Signals are owned by price_pusher.main: uvicorn must not swap the
        # SIGTERM/SIGINT handlers nor stop serving before the orchestrator
        # has shut down.
        yield


class FastAPIHealthServer:
    """
    FastAPI health server: /health is liveness (the process makes progress),
    /ready is readiness (it pushed recently), /metrics is Prometheus.
    """

    def __init__(
        self,
        port: int = 8080,
        max_seconds_without_push: int = 300,
        max_seconds_without_poll: int = 300,
        metrics: PrometheusMetrics | None = None,
    ):
        self.port = port
        self.status = HealthStatus(
            max_seconds_without_push=max_seconds_without_push,
            max_seconds_without_poll=max_seconds_without_poll,
        )
        self.metrics = metrics or PrometheusMetrics()
        self.app = FastAPI(title="Price Pusher Health Server", version="1.0.0")
        self._server: Optional[_Server] = None
        self._serve_task: Optional[asyncio.Task] = None
        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/health")
        @self.app.get("/healthz")
        @self.app.get("/")
        async def health_check():
            code, body = self.status.liveness()
            return JSONResponse(content=body, status_code=code)

        @self.app.get("/ready")
        async def readiness_check():
            code, body = self.status.readiness()
            return JSONResponse(content=body, status_code=code)

        @self.app.get("/metrics")
        async def metrics():
            """Prometheus exposition: fetcher rejections, deviations, reference
            failures, stablecoin prices, pushes. Scraped by the PodMonitor."""
            body, content_type = self.metrics.exposition()
            return Response(content=body, media_type=content_type)

        @self.app.get("/metrics/json")
        async def metrics_json():
            """Basic metrics endpoint (legacy JSON)"""
            now = time.time()
            status = self.status
            return JSONResponse(
                content={
                    "uptime_seconds": int(now - status.startup_time),
                    "total_pushes": status.total_pushes,
                    "last_push_timestamp": status.last_push_timestamp,
                    "last_push_seconds_ago": int(now - status.last_push_timestamp)
                    if status.last_push_timestamp
                    else None,
                    "last_poll_seconds_ago": int(now - status.last_poll_timestamp)
                    if status.last_poll_timestamp
                    else None,
                    "max_seconds_without_push": status.max_seconds_without_push,
                    "max_seconds_without_poll": status.max_seconds_without_poll,
                },
                status_code=200,
            )

    def update_last_push(self) -> None:
        """Called by pusher after successful push"""
        self.status.record_push()
        self.metrics.push_succeeded()
        logger.debug(
            f"FastAPI Health server: Push #{self.status.total_pushes} recorded"
        )

    async def start(self) -> None:
        """Bind the port and serve in the background; returns once listening."""
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info",
            access_log=False,
        )
        self._server = _Server(config)
        self._serve_task = asyncio.create_task(self._server.serve())
        while not self._server.started:
            if self._serve_task.done():
                # A bind failure ends serve() early: surface it instead of
                # looping forever.
                self._serve_task.result()
                raise RuntimeError(
                    f"health server exited before binding port {self.port}"
                )
            await asyncio.sleep(0.05)
        logger.info(f"🏥 FastAPI Health server started on port {self.port}")

    async def stop(self) -> None:
        if self._server is None or self._serve_task is None:
            return
        self._server.should_exit = True
        await self._serve_task

    def get_app(self) -> FastAPI:
        """Get the FastAPI app instance for external server management"""
        return self.app
