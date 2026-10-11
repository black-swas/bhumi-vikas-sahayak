"""Process-wide requests-per-minute limiter (sliding 60 s window). In memory, per instance."""

import threading
import time
from collections import deque
from collections.abc import Callable

from .port import LLMError


class RpmLimiter:
    def __init__(
        self,
        rpm: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.rpm = max(1, rpm)
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, max_wait_s: float = 20.0) -> float:
        """Block until a slot is free; return seconds waited. Raises past ``max_wait_s``."""
        start = self._clock()
        while True:
            with self._lock:
                now = self._clock()
                while self._calls and now - self._calls[0] >= 60.0:
                    self._calls.popleft()
                if len(self._calls) < self.rpm:
                    self._calls.append(now)
                    return now - start
                wait = 60.0 - (now - self._calls[0])
            if (self._clock() - start) + wait > max_wait_s:
                raise LLMError("rate_limit", "local limiter: no slot within the wait budget")
            self._sleep(min(wait, 1.0) if wait > 1.0 else wait)


_LIMITERS: dict[str, RpmLimiter] = {}
_LIMITERS_LOCK = threading.Lock()


def get_limiter(name: str, rpm: int) -> RpmLimiter:
    """One limiter per name (model) for the whole process."""
    with _LIMITERS_LOCK:
        lim = _LIMITERS.get(name)
        if lim is None or lim.rpm != max(1, rpm):
            lim = _LIMITERS[name] = RpmLimiter(rpm)
        return lim
