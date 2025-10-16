import time
import logging
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

logger = logging.getLogger(__name__)


class FastAPIHealthServer:
    """
    FastAPI-based health check server that monitors the price pusher service.
    Returns healthy status while warming up, then monitors push frequency.
    """

    def __init__(self, port: int = 8080, max_seconds_without_push: int = 300):
        """
        Initialize the FastAPI health server.

        Args:
            port: Port to run the health server on
            max_seconds_without_push: Maximum seconds without a push before unhealthy
        """
        self.port = port
        self.last_push_timestamp: Optional[float] = None
        self.max_seconds_without_push = max_seconds_without_push
        self.startup_time = time.time()
        self.total_pushes = 0
        self.app = FastAPI(title="Price Pusher Health Server", version="1.0.0")
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes for health checks"""

        @self.app.get("/health")
        @self.app.get("/healthz")
        @self.app.get("/")
        async def health_check():
            """
            Health check endpoint.

            Returns:
                - 200 (healthy) if warming up or push within threshold
                - 503 (unhealthy) if no push for too long after first push
            """
            # No push yet = still warming up = healthy
            if not self.last_push_timestamp:
                seconds_since_startup = time.time() - self.startup_time
                return JSONResponse(
                    content={
                        "status": "healthy",
                        "state": "warming_up",
                        "seconds_since_startup": int(seconds_since_startup),
                        "total_pushes": 0,
                        "message": f"Waiting for first push ({int(seconds_since_startup)}s since startup)",
                    },
                    status_code=200,
                )

            # We have pushed at least once
            seconds_since_push = time.time() - self.last_push_timestamp

            if seconds_since_push > self.max_seconds_without_push:
                return JSONResponse(
                    content={
                        "status": "unhealthy",
                        "state": "stale",
                        "last_push_seconds_ago": int(seconds_since_push),
                        "max_allowed_seconds": self.max_seconds_without_push,
                        "total_pushes": self.total_pushes,
                        "message": f"No push for {int(seconds_since_push)} seconds",
                    },
                    status_code=503,
                )

            return JSONResponse(
                content={
                    "status": "healthy",
                    "state": "active",
                    "last_push_seconds_ago": int(seconds_since_push),
                    "max_allowed_seconds": self.max_seconds_without_push,
                    "total_pushes": self.total_pushes,
                },
                status_code=200,
            )

        @self.app.get("/ready")
        async def readiness_check():
            """
            Readiness check endpoint.
            Returns ready if the service has pushed at least once.
            """
            if not self.last_push_timestamp:
                seconds_since_startup = time.time() - self.startup_time
                return JSONResponse(
                    content={
                        "status": "not_ready",
                        "state": "warming_up",
                        "seconds_since_startup": int(seconds_since_startup),
                        "total_pushes": 0,
                        "message": f"Service not ready yet ({int(seconds_since_startup)}s since startup)",
                    },
                    status_code=503,
                )

            seconds_since_push = time.time() - self.last_push_timestamp

            if seconds_since_push > self.max_seconds_without_push:
                return JSONResponse(
                    content={
                        "status": "not_ready",
                        "state": "stale",
                        "last_push_seconds_ago": int(seconds_since_push),
                        "max_allowed_seconds": self.max_seconds_without_push,
                        "total_pushes": self.total_pushes,
                        "message": f"Service stale - no push for {int(seconds_since_push)} seconds",
                    },
                    status_code=503,
                )

            return JSONResponse(
                content={
                    "status": "ready",
                    "state": "active",
                    "last_push_seconds_ago": int(seconds_since_push),
                    "total_pushes": self.total_pushes,
                },
                status_code=200,
            )

        @self.app.get("/metrics")
        async def metrics():
            """Basic metrics endpoint"""
            current_time = time.time()
            return JSONResponse(
                content={
                    "uptime_seconds": int(current_time - self.startup_time),
                    "total_pushes": self.total_pushes,
                    "last_push_timestamp": self.last_push_timestamp,
                    "last_push_seconds_ago": int(
                        current_time - self.last_push_timestamp
                    )
                    if self.last_push_timestamp
                    else None,
                    "max_seconds_without_push": self.max_seconds_without_push,
                },
                status_code=200,
            )

    def update_last_push(self) -> None:
        """Called by pusher after successful push"""
        self.last_push_timestamp = time.time()
        self.total_pushes += 1
        logger.debug(f"FastAPI Health server: Push #{self.total_pushes} recorded")

    async def start(self) -> None:
        """Start the FastAPI health check server"""
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)

        logger.info(f"🏥 FastAPI Health server started on port {self.port}")
        await server.serve()

    def get_app(self) -> FastAPI:
        """Get the FastAPI app instance for external server management"""
        return self.app
