"""Celery application — task broker configuration.

Broker  : Redis  (queue + pub/sub)
Backend : Redis  (result storage, separate DB index)
"""

from __future__ import annotations

from celery import Celery

from src.config import settings

# Use DB 0 for broker, DB 1 for results
_broker = settings.redis_url                              # redis://redis:6379/0
_backend = settings.redis_url.replace("/0", "/1", 1)     # redis://redis:6379/1

app = Celery(
    "moneymaker",
    broker=_broker,
    backend=_backend,
    include=["workers.tasks"],
)

app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Visibility
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    # Result TTL
    result_expires=3600,
    # Beat schedule — one cycle every LOOP_INTERVAL_HOURS
    beat_schedule={
        "autonomous-cycle": {
            "task": "trigger_cycle",
            "schedule": settings.loop_interval_hours * 3600,  # seconds
            "kwargs": {
                "sources": ["reddit", "producthunt", "indiehackers", "jobboards"],
                "limit": settings.loop_signal_limit,
            },
        },
    },
)
