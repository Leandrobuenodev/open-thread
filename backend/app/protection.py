"""Bounded, process-local chat admission; no waiting for inference capacity."""

import math
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock

from app.auth import AuthenticatedUser


def positive_integer(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError(f"{name} must be a positive integer.") from None
    if value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


@dataclass(frozen=True)
class ChatLimits:
    requests_per_window: int = 5
    window_seconds: int = 60
    max_concurrency: int = 1
    body_bytes: int = 64 * 1024
    message_bytes: int = 512
    output_tokens: int = 256

    @classmethod
    def from_environment(cls) -> "ChatLimits":
        return cls(
            requests_per_window=positive_integer("CHAT_RATE_LIMIT_REQUESTS", 5),
            window_seconds=positive_integer("CHAT_RATE_LIMIT_WINDOW_SECONDS", 60),
            max_concurrency=positive_integer("CHAT_MAX_CONCURRENCY", 1),
            body_bytes=positive_integer("CHAT_MAX_BODY_BYTES", 64 * 1024),
            message_bytes=positive_integer("CHAT_MAX_MESSAGE_BYTES", 512),
            output_tokens=positive_integer("FOUNDRY_MAX_OUTPUT_TOKENS", 256),
        )


class ChatThrottled(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many requests. Please try again later.")
        self.retry_after = retry_after


class ChatAdmission:
    # Refuse new identities when full rather than growing indefinitely or
    # evicting live counters (which would let users bypass their rate limit).
    MAX_TRACKED_USERS = 10_000

    def __init__(
        self, limits: ChatLimits, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limits = limits
        self._clock = clock
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}
        self._active: set[tuple[str, str]] = set()
        self._lock = Lock()

    @contextmanager
    def admit(self, user: AuthenticatedUser) -> Iterator[None]:
        identity = (user.tenant_id, user.object_id)
        with self._lock:
            now = self._clock()
            self._windows = {
                key: window for key, window in self._windows.items() if window[0] > now
            }
            window = self._windows.get(identity)
            if window is None:
                if len(self._windows) >= self.MAX_TRACKED_USERS:
                    delay = min(expiry for expiry, _ in self._windows.values()) - now
                    raise ChatThrottled(max(1, math.ceil(delay)))
                window = (now + self.limits.window_seconds, 0)
            expiry, count = window
            if count >= self.limits.requests_per_window:
                raise ChatThrottled(max(1, math.ceil(expiry - now)))
            # Count valid authenticated attempts, including capacity rejections
            # and upstream failures, so aggressive retries do not bypass limits.
            self._windows[identity] = (expiry, count + 1)
            if (
                identity in self._active
                or len(self._active) >= self.limits.max_concurrency
            ):
                raise ChatThrottled(1)
            self._active.add(identity)
        try:
            yield
        finally:
            with self._lock:
                self._active.remove(identity)
