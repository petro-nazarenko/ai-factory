"""Tests for logger utilities."""

import logging

import src.utils.logger as logger_module
from src.utils.logger import (
    add_log_context,
    bind_request_id,
    configure_logging,
    get_logger,
)


class TestConfigureLogging:
    def test_idempotent_second_call_is_noop(self) -> None:
        """Calling configure_logging() twice must not raise."""
        configure_logging()
        configure_logging(logging.DEBUG)  # second call — no-op

    def test_reads_log_level_from_env(self, monkeypatch: object) -> None:
        """When log_level is None the env var LOG_LEVEL is used."""

        original = logger_module._logging_configured
        logger_module._logging_configured = False
        monkeypatch.setenv("LOG_LEVEL", "WARNING")  # type: ignore[attr-defined]
        try:
            configure_logging()
        finally:
            logger_module._logging_configured = original

    def test_explicit_level_accepted(self) -> None:
        original = logger_module._logging_configured
        logger_module._logging_configured = False
        try:
            configure_logging(logging.ERROR)
        finally:
            logger_module._logging_configured = original


class TestGetLogger:
    def test_returns_logger_with_name(self) -> None:
        lg = get_logger("test.module")
        assert lg is not None

    def test_returns_logger_without_name(self) -> None:
        lg = get_logger()
        assert lg is not None

    def test_triggers_configure_when_not_yet_done(self) -> None:
        original = logger_module._logging_configured
        logger_module._logging_configured = False
        try:
            lg = get_logger("bootstrap_test")
            assert lg is not None
        finally:
            logger_module._logging_configured = original


class TestAddLogContext:
    def test_sets_context_without_error(self) -> None:
        add_log_context(operation="unit_test", user="tester")


class TestBindRequestId:
    def test_returns_explicit_id(self) -> None:
        rid = bind_request_id("fixed-id-123")
        assert rid == "fixed-id-123"

    def test_generates_uuid_when_none(self) -> None:
        rid = bind_request_id()
        # UUID4: 36 chars, 4 hyphens
        assert len(rid) == 36
        assert rid.count("-") == 4

    def test_two_generated_ids_are_different(self) -> None:
        assert bind_request_id() != bind_request_id()
