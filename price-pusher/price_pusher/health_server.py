import time
import logging
from typing import Optional
from aiohttp import web

logger = logging.getLogger(__name__)


class HealthServer:
    """
    Health check server that monitors the price pusher service.
    Returns healthy status while warming up, then monitors push frequency.
    """

    def __init__(self, port: int = 8080, max_seconds_without_push: int = 300):
        """
        Initialize the health server.

        Args:
            port: Port to run the health server on
            max_seconds_without_push: Maximum seconds without a push before unhealthy
        """
        self.port = port
        self.last_push_timestamp: Optional[float] = None
        self.max_seconds_without_push = max_seconds_without_push
        self.startup_time = time.time()
        self.total_pushes = 0

    def update_last_push(self) -> None:
        """Called by pusher after successful push"""
        self.last_push_timestamp = time.time()
        self.total_pushes += 1
        logger.debug(f"Health server: Push #{self.total_pushes} recorded")

    async def health_check(self, request) -> web.Response:
        """
        Health check endpoint.

        Returns:
            - 200 (healthy) if warming up or push within threshold
            - 503 (unhealthy) if no push for too long after first push
        """
        # No push yet = still warming up = healthy
        if not self.last_push_timestamp:
            seconds_since_startup = time.time() - self.startup_time
            return web.json_response(
                {
                    "status": "healthy",
                    "state": "warming_up",
                    "seconds_since_startup": int(seconds_since_startup),
                    "total_pushes": 0,
                    "message": f"Waiting for first push ({int(seconds_since_startup)}s since startup)",
                },
                status=200,
            )

        # We have pushed at least once
        seconds_since_push = time.time() - self.last_push_timestamp

        if seconds_since_push > self.max_seconds_without_push:
            return web.json_response(
                {
                    "status": "unhealthy",
                    "state": "stale",
                    "last_push_seconds_ago": int(seconds_since_push),
                    "max_allowed_seconds": self.max_seconds_without_push,
                    "total_pushes": self.total_pushes,
                    "message": f"No push for {int(seconds_since_push)} seconds",
                },
                status=503,
            )

        return web.json_response(
            {
                "status": "healthy",
                "state": "active",
                "last_push_seconds_ago": int(seconds_since_push),
                "max_allowed_seconds": self.max_seconds_without_push,
                "total_pushes": self.total_pushes,
            },
            status=200,
        )

    async def start(self) -> None:
        """Start the health check HTTP server"""
        app = web.Application()
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/healthz", self.health_check)  # k8s convention
        app.router.add_get("/", self.health_check)  # root endpoint

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()

        logger.info(f"🏥 Health server started on port {self.port}")
