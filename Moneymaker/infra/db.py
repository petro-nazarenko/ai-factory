"""PostgreSQL async engine and session factory.

Usage
-----
    from infra.db import get_session

    async with get_session() as session:
        session.add(record)
        await session.commit()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

_SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all ORM-mapped tables (idempotent)."""
    from core.schema import Base  # local import to avoid circular

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
