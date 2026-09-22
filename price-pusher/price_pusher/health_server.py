import logging

from typing import Optional

from aiohttp import web

from price_pusher.health import HealthStatus

logger = logging.getLogger(__name__)


class HealthServer:
    """
    aiohttp health server (legacy): /health is liveness (the process makes
    progress), /ready is readiness (it pushed recently).
    """

    def __init__(
        self,
        port: int = 8080,
        max_seconds_without_push: int = 300,
        max_seconds_without_poll: int = 300,
    ):
        self.port = port
        self.status = HealthStatus(
            max_seconds_without_push=max_seconds_without_push,
            max_seconds_without_poll=max_seconds_without_poll,
        )
        self._runner: Optional[web.AppRunner] = None

    def update_last_push(self) -> None:
        """Called by pusher after successful push"""
        self.status.record_push()
        logger.debug(f"Health server: Push #{self.status.total_pushes} recorded")

    async def health_check(self, request) -> web.Response:
        code, body = self.status.liveness()
        return web.json_response(body, status=code)

    async def readiness_check(self, request) -> web.Response:
        code, body = self.status.readiness()
        return web.json_response(body, status=code)

    async def start(self) -> None:
        """Bind the port and serve in the background; returns once listening."""
        app = web.Application()
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/healthz", self.health_check)  # k8s convention
        app.router.add_get("/", self.health_check)  # root endpoint
        app.router.add_get("/ready", self.readiness_check)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()

        logger.info(f"🏥 Health server started on port {self.port}")

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
