"""Redis async client factory.

Provides a single shared connection pool used by the event bus,
caching, and Celery result storage.

Usage
-----
    from infra.redis_client import get_client

    r = get_client()
    await r.publish("signal_found", payload_json)
"""

from __future__ import annotations

import redis.asyncio as aioredis

from src.config import settings

_pool: aioredis.ConnectionPool | None = None


def _get_pool() -> aioredis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=True,
        )
    return _pool


def get_client() -> aioredis.Redis:
    """Return a Redis client backed by the shared pool."""
    return aioredis.Redis(connection_pool=_get_pool())


async def publish(channel: str, message: str) -> None:
    """Publish a JSON string message to a Redis pub/sub channel."""
    await get_client().publish(channel, message)
