"""Base integration classes and common patterns."""

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import tenacity
from tenacity import (
    RetryCallState,
    stop_after_attempt,
)

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class IntegrationError(Exception):
    """Base exception for integration errors."""


class RateLimitError(IntegrationError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(IntegrationError):
    """Raised when authentication fails."""


class IntegrationConnectionError(IntegrationError):
    """Raised when connection fails."""


class _TokenBucket:
    """Thread-safe token-bucket rate limiter.

    Tokens refill at *rate* per second up to *capacity*.  Call ``acquire()``
    before each outbound request; it blocks until a token is available.

    Args:
        rate: Tokens added per second (= maximum sustained requests/s).
        capacity: Burst capacity (defaults to *rate*, i.e. no burst).
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = rate
        self._capacity = capacity if capacity is not None else rate
        self._tokens = self._capacity
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available, then consume it."""
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self._rate
                )
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            # Sleep outside the lock so other threads can proceed.
            time.sleep(wait)


@dataclass
class IntegrationConfig:
    """Base configuration for integrations."""

    max_retries: int = 3
    timeout: float = 30.0
    rate_limit_delay: float = 1.0
    #: Maximum outbound requests per second (0 = unlimited / no throttle).
    requests_per_second: float = 0.0


class BaseIntegration(ABC):
    """Abstract base class for integrations.

    Provides common patterns:
    - Exponential backoff retry logic
    - Rate limiting awareness
    - Connection management
    - Standardized logging
    """

    def __init__(self, config: IntegrationConfig | None = None) -> None:
        self._config = config or IntegrationConfig()
        self._connected = False
        self._logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._bucket: _TokenBucket | None = (
            _TokenBucket(self._config.requests_per_second)
            if self._config.requests_per_second > 0
            else None
        )

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the name of the service."""
        raise NotImplementedError

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the service."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the service."""
        raise NotImplementedError

    def __enter__(self) -> "BaseIntegration":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()

    def _throttle(self) -> None:
        """Pace outgoing requests to the configured rate.

        Call once before each outbound API request.  When
        ``IntegrationConfig.requests_per_second`` is 0 (the default) this is a
        no-op.  When a positive rate is set this blocks until the token bucket
        has a token available, ensuring the sustained request rate never exceeds
        the configured limit.

        Example::

            def fetch_data(self) -> dict:
                self._throttle()          # pace before hitting the API
                return self._client.get("/data")
        """
        if self._bucket is not None:
            self._bucket.acquire()

    def retry_with_backoff(
        self,
        max_attempts: int | None = None,
        initial_wait: float = 1.0,
        max_wait: float = 60.0,
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator for retry with exponential backoff.

        Args:
            max_attempts: Maximum number of retry attempts
            initial_wait: Initial wait time in seconds
            max_wait: Maximum wait time in seconds

        Returns:
            Decorated function with retry logic
        """
        if max_attempts is None:
            max_attempts = self._config.max_retries

        stop_strategy = stop_after_attempt(max_attempts)
        wait_strategy = tenacity.wait_exponential(
            multiplier=initial_wait,
            max=max_wait,
        )

        def before_callback(retry_state: RetryCallState) -> None:
            """Log retry attempts."""
            attempt = retry_state.attempt_number
            exception = retry_state.outcome.exception() if retry_state.outcome else None
            self._logger.warning(
                f"Retry attempt {attempt}/{max_attempts} for {self.service_name}",
                extra={"exception": str(exception) if exception else None},
            )

        return tenacity.retry(
            stop=stop_strategy,
            wait=wait_strategy,
            before_sleep=before_callback,
            reraise=True,
        )

    def _handle_rate_limit(self, response: Any) -> None:
        """Handle rate limit response with automatic backoff.

        If the response carries a 429 status, waits for the ``Retry-After``
        interval (default: ``rate_limit_delay``) before raising
        ``RateLimitError`` so the caller's retry logic gets a real chance to
        succeed.

        Args:
            response: API response object

        Raises:
            RateLimitError: When rate limit is exceeded
        """
        if hasattr(response, "status_code") and response.status_code == 429:
            retry_after_raw = response.headers.get("Retry-After")
            retry_after = int(retry_after_raw) if retry_after_raw else None
            wait = retry_after if retry_after is not None else self._config.rate_limit_delay
            self._logger.warning(
                "rate_limit_hit",
                wait_seconds=wait,
                retry_after=retry_after,
            )
            time.sleep(wait)
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=retry_after,
            )

    def _validate_config(self) -> None:
        """Validate integration configuration."""
        if self._config.max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        if self._config.timeout <= 0:
            raise ValueError("timeout must be positive")
        if self._config.rate_limit_delay < 0:
            raise ValueError("rate_limit_delay cannot be negative")

    @property
    def is_connected(self) -> bool:
        """Check if integration is connected."""
        return self._connected
