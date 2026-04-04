"""Tests for configuration validators."""

import pytest
from pydantic import ValidationError

from src.utils.config import AppSettings, EmailSettings, load_config


class TestEmailSettingsPortValidator:
    def test_port_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Port must be between"):
            EmailSettings(smtp_port=0)

    def test_port_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Port must be between"):
            EmailSettings(imap_port=65536)

    def test_valid_port_accepted(self) -> None:
        s = EmailSettings(smtp_port=465, imap_port=993)
        assert s.smtp_port == 465
        assert s.imap_port == 993


class TestAppSettingsLogLevelValidator:
    def test_invalid_level_rejected(self) -> None:
        with pytest.raises(ValidationError, match="log_level must be one of"):
            AppSettings(log_level="VERBOSE")

    def test_lowercase_normalised_to_upper(self) -> None:
        s = AppSettings(log_level="debug")
        assert s.log_level == "DEBUG"

    def test_mixed_case_normalised(self) -> None:
        s = AppSettings(log_level="Warning")
        assert s.log_level == "WARNING"


class TestAppSettingsEnvironmentValidator:
    def test_invalid_env_rejected(self) -> None:
        with pytest.raises(ValidationError, match="environment must be one of"):
            AppSettings(environment="qa")

    def test_uppercase_normalised_to_lower(self) -> None:
        s = AppSettings(environment="PRODUCTION")
        assert s.environment == "production"

    def test_staging_accepted(self) -> None:
        s = AppSettings(environment="staging")
        assert s.environment == "staging"


class TestLoadConfig:
    def test_returns_settings_instance(self) -> None:
        from src.utils.config import Settings

        settings = load_config()
        assert isinstance(settings, Settings)

    def test_is_cached(self) -> None:
        s1 = load_config()
        s2 = load_config()
        assert s1 is s2
