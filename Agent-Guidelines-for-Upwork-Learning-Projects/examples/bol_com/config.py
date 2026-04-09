"""Configuration for Bol.com example."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration settings."""

    BOL_CLIENT_ID: str
    BOL_CLIENT_SECRET: str
    BOL_ACCESS_TOKEN: str | None
    GOOGLE_SHEETS_CREDENTIALS: str
    GOOGLE_SHEETS_SPREADSHEET_ID: str


def _get_config() -> Config:
    """Load configuration from environment variables."""
    return Config(
        BOL_CLIENT_ID=os.getenv("BOL_CLIENT_ID", ""),
        BOL_CLIENT_SECRET=os.getenv("BOL_CLIENT_SECRET", ""),
        BOL_ACCESS_TOKEN=os.getenv("BOL_ACCESS_TOKEN"),
        GOOGLE_SHEETS_CREDENTIALS=os.getenv("GOOGLE_SHEETS_CREDENTIALS", "config/credentials.json"),
        GOOGLE_SHEETS_SPREADSHEET_ID=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", ""),
    )


config = _get_config()
