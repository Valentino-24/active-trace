"""In-memory rate limiter for login attempts.

Tracks failed attempts per IP+email combination.
Simple dict-based implementation — sufficient for MVP.
Migrate to Redis when multi-instance is needed.
"""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """Sliding-window rate limiter keyed by (ip, email).

    Tracks timestamps of attempts within a configurable window.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60) -> None:
        """Initialize the rate limiter.

        Args:
            max_attempts: Maximum allowed attempts per window.
            window_seconds: Sliding window duration in seconds.
        """
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _cleanup(self, key: tuple[str, str]) -> None:
        """Remove timestamps outside the current window."""
        now = time.time()
        cutoff = now - self._window_seconds
        self._attempts[key] = [
            ts for ts in self._attempts[key] if ts > cutoff
        ]
        if not self._attempts[key]:
            del self._attempts[key]

    def _record(self, key: tuple[str, str]) -> None:
        """Record an attempt timestamp."""
        self._attempts[key].append(time.time())

    def check(self, ip: str, email: str) -> bool:
        """Check if an attempt is allowed.

        Returns True if allowed (under limit), False if rate-limited.
        Also records the attempt.
        """
        key = (ip, email)
        self._cleanup(key)
        if len(self._attempts.get(key, [])) >= self._max_attempts:
            return False
        self._record(key)
        return True

    def get_remaining(self, ip: str, email: str) -> int:
        """Get remaining attempts before rate limit is hit.

        Returns:
            Number of remaining attempts (0 if rate-limited).
        """
        key = (ip, email)
        self._cleanup(key)
        current = len(self._attempts.get(key, []))
        return max(0, self._max_attempts - current)

    def reset(self, ip: str, email: str) -> None:
        """Clear all attempt records for a given IP+email."""
        key = (ip, email)
        self._attempts.pop(key, None)
