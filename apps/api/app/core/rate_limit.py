from collections import defaultdict, deque
from time import monotonic
from threading import Lock

from fastapi import HTTPException, Request

from app.config import get_settings


class InMemoryRateLimiter:
    def __init__(self):
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        settings = get_settings()
        now = monotonic()
        cutoff = now - settings.rate_limit_window_seconds
        with self._lock:
            requests = self._requests[key]
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if len(requests) >= settings.rate_limit_requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            requests.append(now)

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


limiter = InMemoryRateLimiter()


def rate_limit(request: Request) -> None:
    limiter.check(request.client.host if request.client else "unknown")
