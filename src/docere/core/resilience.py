"""Retry and circuit breaker utilities for external service calls.

Usage:
    breaker = CircuitBreaker("openai")

    result = await breaker.call(
        lambda: openai_client.chat.completions.create(...)
    )

    # Or with the retry decorator:
    @with_retry(max_retries=3)
    async def my_flaky_call():
        ...
"""

import asyncio
import random
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any

import structlog

logger = structlog.get_logger()


class CircuitState(Enum):
    CLOSED = "closed"  # Normal — requests pass through
    OPEN = "open"  # Tripped — requests fail fast
    HALF_OPEN = "half_open"  # Testing — one request allowed through


class CircuitOpenError(RuntimeError):
    """Raised when circuit breaker is open and blocking requests."""

    def __init__(self, service: str, retry_after: float):
        self.service = service
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker open for {service}. Retry after {retry_after:.0f}s.")


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for external services.

    State machine:
      CLOSED  → (failure_threshold failures) → OPEN
      OPEN    → (recovery_timeout elapsed)   → HALF_OPEN
      HALF_OPEN → (success)                  → CLOSED
      HALF_OPEN → (failure)                  → OPEN
    """

    service: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        # Auto-transition from OPEN → HALF_OPEN after recovery timeout
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def call(self, fn: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        """Execute fn through the circuit breaker."""
        state = self.state

        if state == CircuitState.OPEN:
            retry_after = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
            raise CircuitOpenError(self.service, max(0, retry_after))

        try:
            result = await fn()
        except Exception as e:
            self._on_failure(e)
            raise
        else:
            self._on_success()
            return result

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered", service=self.service)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def _on_failure(self, error: Exception) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Recovery test failed — back to OPEN
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker re-opened (half-open test failed)",
                service=self.service,
                error=str(error),
            )
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(
                "Circuit breaker opened",
                service=self.service,
                failures=self._failure_count,
                error=str(error),
            )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0


async def retry_async(
    fn: Callable[[], Coroutine[Any, Any, Any]],
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    retryable: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """Retry an async function with exponential backoff and jitter.

    Args:
        fn: Async callable (zero-arg lambda or function).
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1).
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap.
        retryable: Exception types that trigger a retry.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except retryable as e:
            last_error = e
            if attempt == max_retries:
                raise
            delay = min(base_delay * (2**attempt), max_delay)
            jitter = delay * (0.5 + random.random() * 0.5)
            logger.warning(
                "Retrying after error",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay=f"{jitter:.1f}s",
                error=str(e),
            )
            await asyncio.sleep(jitter)

    raise last_error  # Should never reach here, but satisfies type checker


def with_retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    retryable: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator version of retry_async."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await retry_async(
                lambda: fn(*args, **kwargs),
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable=retryable,
            )

        return wrapper

    return decorator
