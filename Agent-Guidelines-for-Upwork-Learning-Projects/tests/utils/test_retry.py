"""Tests for retry utilities."""

import concurrent.futures
import threading
import time

import pytest

from src.utils.retry import with_retry, with_timeout


class TestWithRetry:
    """Tests for retry decorator."""

    def test_success_on_first_attempt(self) -> None:
        """Test successful function without retry."""
        call_count = 0

        @with_retry(max_attempts=3)
        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure(self) -> None:
        """Test retry on transient failure."""
        call_count = 0

        @with_retry(max_attempts=3, initial_wait=0.01)
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 3

    def test_raises_after_max_attempts(self) -> None:
        """Test that exception is raised after max attempts."""
        call_count = 0

        @with_retry(max_attempts=3, initial_wait=0.01)
        def always_fail() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            always_fail()

        assert call_count == 3

    def test_retry_specific_exceptions(self) -> None:
        """Test retry only on specific exceptions."""
        call_count = 0

        @with_retry(max_attempts=3, exceptions=(ConnectionError,))
        def mixed_failures() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Not retryable")
            if call_count == 2:
                raise ConnectionError("Retryable")
            return "success"

        with pytest.raises(ValueError, match="Not retryable"):
            mixed_failures()

        assert call_count == 1


class TestWithTimeout:
    """Tests for timeout decorator."""

    def test_function_completes_within_timeout(self) -> None:
        """Test that function completes normally when within timeout."""

        @with_timeout(seconds=5.0)
        def fast_func() -> str:
            return "done"

        result = fast_func()
        assert result == "done"

    def test_function_raises_on_timeout(self) -> None:
        """Test that TimeoutError is raised when function exceeds timeout."""

        @with_timeout(seconds=0.1)
        def slow_func() -> str:
            time.sleep(10)
            return "never"

        with pytest.raises(concurrent.futures.TimeoutError):
            slow_func()

    def test_works_in_thread(self) -> None:
        """Test that with_timeout works correctly when called from a thread."""
        results: list[str] = []

        @with_timeout(seconds=5.0)
        def threaded_func() -> str:
            return "thread_result"

        def run_in_thread() -> None:
            results.append(threaded_func())

        t = threading.Thread(target=run_in_thread)
        t.start()
        t.join(timeout=10)

        assert results == ["thread_result"]

    def test_preserves_function_name(self) -> None:
        """Test that decorator preserves the wrapped function name."""

        @with_timeout(seconds=5.0)
        def my_named_func() -> None:
            pass

        assert my_named_func.__name__ == "my_named_func"
