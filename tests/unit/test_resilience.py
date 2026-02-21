"""Tests for retry and circuit breaker utilities."""

import asyncio
import time

import pytest

from docere.core.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    retry_async,
)


# ── retry_async ──


class TestRetryAsync:
    async def test_succeeds_first_try(self):
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            return "ok"

        result = await retry_async(fn, max_retries=3)
        assert result == "ok"
        assert calls == 1

    async def test_retries_on_transient_failure(self):
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = await retry_async(
            fn, max_retries=3, base_delay=0.01, retryable=(ConnectionError,)
        )
        assert result == "recovered"
        assert calls == 3

    async def test_raises_after_max_retries(self):
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            raise ConnectionError("permanent")

        with pytest.raises(ConnectionError, match="permanent"):
            await retry_async(
                fn, max_retries=2, base_delay=0.01, retryable=(ConnectionError,)
            )
        assert calls == 3  # initial + 2 retries

    async def test_does_not_retry_non_retryable(self):
        calls = 0

        async def fn():
            nonlocal calls
            calls += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await retry_async(
                fn, max_retries=3, base_delay=0.01, retryable=(ConnectionError,)
            )
        assert calls == 1  # No retry for ValueError

    async def test_exponential_backoff_timing(self):
        """Verify retries take progressively longer."""
        calls = []

        async def fn():
            calls.append(time.monotonic())
            if len(calls) < 3:
                raise ConnectionError("fail")
            return "ok"

        await retry_async(
            fn, max_retries=3, base_delay=0.05, retryable=(ConnectionError,)
        )
        assert len(calls) == 3
        # Second delay should be roughly 2x the first (exponential)
        delay1 = calls[1] - calls[0]
        delay2 = calls[2] - calls[1]
        assert delay2 > delay1 * 1.2  # Allow some jitter tolerance


# ── CircuitBreaker ──


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    async def test_success_stays_closed(self):
        cb = CircuitBreaker("test")
        result = await cb.call(self._success)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    async def test_failures_below_threshold_stay_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail)
        assert cb.state == CircuitState.CLOSED

    async def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail)
        assert cb.state == CircuitState.OPEN

    async def test_open_rejects_immediately(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        with pytest.raises(ConnectionError):
            await cb.call(self._fail)
        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(self._success)
        assert exc_info.value.service == "test"

    async def test_transitions_to_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(ConnectionError):
            await cb.call(self._fail)
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN

    async def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(ConnectionError):
            await cb.call(self._fail)

        await asyncio.sleep(0.06)
        result = await cb.call(self._success)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    async def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)
        with pytest.raises(ConnectionError):
            await cb.call(self._fail)

        await asyncio.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN
        with pytest.raises(ConnectionError):
            await cb.call(self._fail)
        assert cb.state == CircuitState.OPEN

    async def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(ConnectionError):
            await cb.call(self._fail)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        # 2 failures
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail)
        # 1 success resets counter
        await cb.call(self._success)
        # 2 more failures should NOT trip (counter was reset)
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await cb.call(self._fail)
        assert cb.state == CircuitState.CLOSED

    # Helpers
    @staticmethod
    async def _success():
        return "ok"

    @staticmethod
    async def _fail():
        raise ConnectionError("service down")
