"""
Liveness and readiness of the price pusher, shared by both health servers.

Liveness answers "is this process making progress?": it is healthy while the
fetchers are being built, then as long as the poll loop keeps completing
rounds. It never depends on pushes: a publisher can legitimately go a long
time without pushing (nothing deviated, nothing outdated), and killing it for
that only produces restart loops.

Readiness answers "has this process pushed recently?", which is what an
operator wants to alert on.
"""

import time

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

HealthResponse = Tuple[int, Dict[str, Any]]


@dataclass
class HealthStatus:
    max_seconds_without_push: int = 300
    max_seconds_without_poll: int = 300
    startup_time: float = field(default_factory=time.time)
    orchestration_started_at: Optional[float] = None
    last_poll_timestamp: Optional[float] = None
    last_push_timestamp: Optional[float] = None
    total_pushes: int = 0

    def orchestration_started(self) -> None:
        self.orchestration_started_at = time.time()

    def record_poll(self) -> None:
        self.last_poll_timestamp = time.time()

    def record_push(self) -> None:
        self.last_push_timestamp = time.time()
        self.total_pushes += 1

    def liveness(self, now: Optional[float] = None) -> HealthResponse:
        now = now if now is not None else time.time()
        if self.orchestration_started_at is None:
            since_startup = int(now - self.startup_time)
            return 200, {
                "status": "healthy",
                "state": "starting",
                "seconds_since_startup": since_startup,
                "total_pushes": 0,
                "message": f"Building fetchers, orchestration not started yet ({since_startup}s since startup)",
            }

        last_progress = self.last_poll_timestamp or self.orchestration_started_at
        since_poll = int(now - last_progress)
        if since_poll > self.max_seconds_without_poll:
            return 503, {
                "status": "unhealthy",
                "state": "stalled",
                "last_poll_seconds_ago": since_poll,
                "max_allowed_seconds": self.max_seconds_without_poll,
                "total_pushes": self.total_pushes,
                "message": f"No completed poll for {since_poll} seconds",
            }

        return 200, {
            "status": "healthy",
            "state": "active",
            "last_poll_seconds_ago": since_poll,
            "last_push_seconds_ago": self._seconds_since_push(now),
            "total_pushes": self.total_pushes,
        }

    def readiness(self, now: Optional[float] = None) -> HealthResponse:
        now = now if now is not None else time.time()
        since_push = self._seconds_since_push(now)
        if since_push is None:
            since_startup = int(now - self.startup_time)
            return 503, {
                "status": "not_ready",
                "state": "warming_up",
                "seconds_since_startup": since_startup,
                "total_pushes": 0,
                "message": f"Service not ready yet ({since_startup}s since startup)",
            }

        if since_push > self.max_seconds_without_push:
            return 503, {
                "status": "not_ready",
                "state": "stale",
                "last_push_seconds_ago": since_push,
                "max_allowed_seconds": self.max_seconds_without_push,
                "total_pushes": self.total_pushes,
                "message": f"Service stale - no push for {since_push} seconds",
            }

        return 200, {
            "status": "ready",
            "state": "active",
            "last_push_seconds_ago": since_push,
            "max_allowed_seconds": self.max_seconds_without_push,
            "total_pushes": self.total_pushes,
        }

    def _seconds_since_push(self, now: float) -> Optional[int]:
        if self.last_push_timestamp is None:
            return None
        return int(now - self.last_push_timestamp)
