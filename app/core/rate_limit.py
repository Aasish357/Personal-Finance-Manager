"""
A small fixed-window rate limiter for the auth endpoints.

Why hand-rolled: it keeps the dependency list unchanged, and the whole policy
is a dozen lines.

Scope and limits -- read this before relying on it for a public deployment:

- State is in-process memory, so limits are per worker process. Running N
  workers behind a load balancer gives each worker its own counter, i.e. N
  times the intended limit. Behind more than one worker, put a shared store
  (Redis, or Postgres via Supabase) in front of this instead.
- Entries are evicted lazily on access rather than swept on a timer, which is
  fine at this scale but means the dict is bounded by distinct keys seen
  within the window.
"""
import threading
import time
from collections import defaultdict

# A fixed window, not a sliding one: simpler, and good enough to blunt
# password guessing without punishing a user who mistypes twice.
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_SECONDS = 300  # 5 minutes


class RateLimiter:
    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        recent = [t for t in self._hits[key] if t > cutoff]
        if recent:
            self._hits[key] = recent
        else:
            # Drop empty keys entirely so the dict doesn't grow forever.
            self._hits.pop(key, None)
        return recent

    def is_blocked(self, key: str) -> tuple[bool, int]:
        """Returns (blocked, seconds_until_retry)."""
        now = time.monotonic()
        with self._lock:
            recent = self._prune(key, now)
            if len(recent) < self.max_attempts:
                return False, 0
            return True, max(1, int(self.window_seconds - (now - recent[0])))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key, time.monotonic())
            self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        """Called on successful login so a legitimate user isn't penalised."""
        with self._lock:
            self._hits.pop(key, None)


# Shared instance used by the auth router.
login_limiter = RateLimiter()