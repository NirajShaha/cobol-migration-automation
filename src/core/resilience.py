"""Resilience utilities — retries with exponential backoff, circuit breaker pattern."""

import asyncio
from functools import wraps
from typing import Callable, TypeVar, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)

from .exceptions import LLMProviderError, LLMRateLimitError
from .logging import get_logger

logger = get_logger("resilience")

T = TypeVar("T")


def with_retries(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (LLMProviderError, LLMRateLimitError, ConnectionError, TimeoutError),
) -> Callable:
    """Decorator for sync functions that should retry on transient failures.
    
    Uses exponential backoff: delay = base_delay * 2^(attempt-1), capped at max_delay.
    """
    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=base_delay, max=max_delay),
            retry=retry_if_exception_type(retryable_exceptions),
            reraise=True,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_with_retries(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = (LLMProviderError, LLMRateLimitError, ConnectionError, TimeoutError),
) -> Callable:
    """Decorator for async functions that should retry on transient failures."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(
                            "retry_scheduled",
                            func=func.__name__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise
            raise last_exception  # Should not reach here
        return wrapper
    return decorator


class CircuitBreaker:
    """Simple circuit breaker to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests fail immediately
    - HALF_OPEN: After cooldown, allow one request to test
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._state = "CLOSED"

    @property
    def state(self) -> str:
        if self._state == "OPEN":
            import time
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.cooldown_seconds:
                self._state = "HALF_OPEN"
        return self._state

    def record_success(self):
        self._failure_count = 0
        self._state = "CLOSED"

    def record_failure(self):
        import time
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "OPEN"
            logger.error(
                "circuit_breaker_opened",
                failures=self._failure_count,
                threshold=self.failure_threshold,
            )

    def can_execute(self) -> bool:
        return self.state != "OPEN"
