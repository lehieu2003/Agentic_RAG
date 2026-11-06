"""Opt-in per-IP request throttling for the API.

A fixed-window counter per (client IP, minute) held in process memory.
Limitations by design: counters are per-worker (not shared across uvicorn
workers) and reset on restart. Disabled while ``RATE_LIMIT_RPM`` is 0.
"""

import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Return 429 once a client IP exceeds ``rpm`` requests per rolling minute."""

    def __init__(self, app, rpm: int, exempt_paths: Tuple[str, ...] = ("/api/v1/health",)) -> None:
        super().__init__(app)
        self.rpm = rpm
        self.exempt_paths = exempt_paths
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.rpm <= 0 or request.url.path in self.exempt_paths:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - 60.0

        hits = self._hits[client_ip]
        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= self.rpm:
            retry_after = max(1, int(60.0 - (now - hits[0])))
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={"detail": f"Rate limit exceeded: max {self.rpm} requests per minute."},
            )

        hits.append(now)

        # Bound the memory used by stale client entries.
        if len(self._hits) > 10_000:
            self._prune(now - 120.0)

        return await call_next(request)

    def _prune(self, older_than: float) -> None:
        stale = [ip for ip, hits in self._hits.items() if not hits or hits[-1] < older_than]
        for ip in stale:
            self._hits.pop(ip, None)
