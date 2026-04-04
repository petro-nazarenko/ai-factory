"""Retry utilities and decorators."""

import concurrent.futures
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import tenacity
from tenacity import RetryCallState

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.

    AuthenticationError is never retried regardless of the ``exceptions``
    argument — retrying auth failures only adds latency before an inevitable
    crash.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        exceptions: Tuple of exceptions to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def before_callback(retry_state: RetryCallState) -> None:
        """Log retry attempts."""
        attempt = retry_state.attempt_number
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        logger.warning(
            "retry_attempt",
            attempt=attempt,
            max_attempts=max_attempts,
            exception=str(exception) if exception else None,
        )

    def should_retry(exc: BaseException) -> bool:
        # Lazy import avoids circular dependency (base.py → src.utils → retry.py → base.py)
        from src.integrations.base import AuthenticationError

        return isinstance(exc, exceptions) and not isinstance(exc, AuthenticationError)

    return tenacity.retry(
        stop=tenacity.stop_after_attempt(max_attempts),
        wait=tenacity.wait_exponential(multiplier=initial_wait, max=max_wait),
        before_sleep=before_callback,
        reraise=True,
        retry=tenacity.retry_if_exception(should_retry),
    )


def with_timeout(seconds: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add timeout to a function.

    Args:
        seconds: Timeout in seconds

    Returns:
        Decorated function with timeout
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(func, *args, **kwargs).result(timeout=seconds)

        return wrapper

    return decorator
