"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleSheetsSettings(BaseSettings):
    """Google Sheets configuration."""

    model_config = SettingsConfigDict(
        env_prefix="GOOGLE_SHEETS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    credentials_path: Path = Field(
        default=Path.home() / ".config" / "upwork-learn" / "credentials.json",
        description="Path to Google service account credentials JSON",
    )
    spreadsheet_id: str | None = Field(
        default=None,
        description="Default spreadsheet ID to use",
    )


class EmailSettings(BaseSettings):
    """Email configuration."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: str | None = Field(default=None)
    smtp_password: SecretStr | None = Field(default=None)

    imap_host: str = Field(default="imap.gmail.com")
    imap_port: int = Field(default=993)
    imap_user: str | None = Field(default=None)
    imap_password: SecretStr | None = Field(default=None)

    @field_validator("smtp_port", "imap_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class APIKeySettings(BaseSettings):
    """API key configuration."""

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    bol_com_api_key: str | None = Field(default=None)
    bol_com_client_id: str | None = Field(default=None)
    bol_com_client_secret: str | None = Field(default=None)


class AppSettings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    log_level: str = Field(default="INFO")
    max_retries: int = Field(default=3, ge=1)
    rate_limit_delay: float = Field(default=1.0, ge=0)
    environment: str = Field(default="development")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return upper

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = {"development", "staging", "production"}
        lower = v.lower()
        if lower not in valid_envs:
            raise ValueError(f"environment must be one of {valid_envs}")
        return lower


class Settings(BaseSettings):
    """Combined application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    google_sheets: GoogleSheetsSettings = Field(default_factory=GoogleSheetsSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    api_keys: APIKeySettings = Field(default_factory=APIKeySettings)
    app: AppSettings = Field(default_factory=AppSettings)


@lru_cache
def load_config() -> Settings:
    """Load and cache application settings.

    Returns:
        Cached Settings instance
    """
    return Settings()
