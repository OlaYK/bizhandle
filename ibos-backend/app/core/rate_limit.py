import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class _RateState:
    failures: list[float] = field(default_factory=list)
    lock_until: float = 0.0


class LoginRateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: int, lock_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self._states: dict[str, _RateState] = {}
        self._lock = Lock()

    def check(self, key: str) -> int:
        """Returns retry-after seconds when blocked, otherwise 0."""
        now = time.time()
        with self._lock:
            state = self._states.get(key)
            if not state:
                return 0
            self._prune(state, now)
            if state.lock_until > now:
                return int(state.lock_until - now) + 1
            return 0

    def register_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            state = self._states.setdefault(key, _RateState())
            self._prune(state, now)
            state.failures.append(now)
            if len(state.failures) >= self.max_attempts:
                state.lock_until = now + self.lock_seconds

    def register_success(self, key: str) -> None:
        with self._lock:
            self._states.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._states.clear()

    def _prune(self, state: _RateState, now: float) -> None:
        cutoff = now - self.window_seconds
        state.failures = [ts for ts in state.failures if ts >= cutoff]
