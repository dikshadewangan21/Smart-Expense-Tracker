"""Small in-memory sliding-window rate limiter.

Limitation: state is per process. With multiple workers/instances, replace the
store with Redis (same interface) or the limits become per-instance.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)
ENABLED = True


def rate_limit(name: str, limit: int, window_seconds: int):
    def dep(request: Request):
        if not ENABLED:
            return
        ip = request.client.host if request.client else "unknown"
        key = f"{name}:{ip}"
        now = time.monotonic()
        q = _hits[key]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Too many attempts. Please wait a moment and try again.")
        q.append(now)

    return dep


def reset():
    _hits.clear()
