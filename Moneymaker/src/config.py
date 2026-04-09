"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Groq (primary LLM provider — optional if ANTHROPIC_API_KEY is set)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # Cerebras (fallback after Groq TPD limit)
    cerebras_api_key: str = Field(default="", alias="CEREBRAS_API_KEY")

    # Anthropic / Claude (optional fallback — only needed if GROQ_API_KEY is absent)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-5-haiku-20241022", alias="ANTHROPIC_MODEL")

    @property
    def has_llm_key(self) -> bool:
        """True if at least one LLM provider key is configured."""
        return bool(self.groq_api_key or self.anthropic_api_key)

    # Reddit
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(
        default="MoneymakerBot/1.0",
        alias="REDDIT_USER_AGENT",
    )

    # Product Hunt
    producthunt_token: str = Field(default="", alias="PRODUCTHUNT_TOKEN")

    # Twitter / X
    twitter_bearer_token: str = Field(default="", alias="TWITTER_BEARER_TOKEN")

    # Telegram
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_id: str = Field(default="", alias="TELEGRAM_CHANNEL_ID")

    # Distribution — Reddit
    reddit_distribution_subreddit: str = Field(
        default="indiehackers",
        alias="REDDIT_DISTRIBUTION_SUBREDDIT",
    )

    # Vercel deployment
    vercel_token: str = Field(default="", alias="VERCEL_TOKEN")
    vercel_team_id: str = Field(default="", alias="VERCEL_TEAM_ID")

    # Autonomous loop
    loop_interval_hours: int = Field(default=24, alias="LOOP_INTERVAL_HOURS")
    loop_signal_limit: int = Field(default=40, alias="LOOP_SIGNAL_LIMIT")

    # Postgres
    database_url: str = Field(
        default="postgresql+asyncpg://user:pass@db:5432/moneymaker",
        alias="DATABASE_URL",
    )

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # SQLite fallback (dev / dry-run)
    db_path: str = Field(default="data/memory.db", alias="DB_PATH")

    # Pipeline
    signal_min_score: float = Field(default=6.0, alias="SIGNAL_MIN_SCORE")
    ideas_per_signal: int = Field(default=3, alias="IDEAS_PER_SIGNAL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


settings = Settings()
