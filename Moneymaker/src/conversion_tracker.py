"""Conversion Tracker — Layer 7 of the MVP Idea Engine.

Records and aggregates conversion events that originate from distribution posts.
Each :class:`ConversionEvent` is linked to a ``tracking_id`` that matches the
``DistributionPost.tracking_id`` field so clicks, sign-ups, replies, and
payments can be attributed to the correct post and platform.

Usage example::

    tracker = ConversionTracker()

    # Record events as they arrive (e.g. from a webhook)
    tracker.record(ConversionEvent(
        tracking_id="abc123",
        event_type=ConversionEventType.CLICK,
        platform=DistributionPlatform.REDDIT,
    ))
    tracker.record(ConversionEvent(
        tracking_id="abc123",
        event_type=ConversionEventType.PAYMENT,
        platform=DistributionPlatform.REDDIT,
        value=49.0,
    ))

    # Query
    summary = tracker.summarize("abc123")
    print(summary.payments, summary.total_revenue)  # 1  49.0

    all_summaries = tracker.summarize_all()
"""

from __future__ import annotations

import logging
from collections import defaultdict

from src.models import (
    ConversionEvent,
    ConversionEventType,
    ConversionSummary,
    DistributionPlatform,
    DistributionResult,
)

logger = logging.getLogger(__name__)


class ConversionTracker:
    """In-memory store of conversion events with aggregation helpers."""

    def __init__(self) -> None:
        # tracking_id → list of events
        self._events: dict[str, list[ConversionEvent]] = defaultdict(list)
        # tracking_id → platform (populated when a post is registered)
        self._platforms: dict[str, DistributionPlatform] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_distribution(self, result: DistributionResult) -> None:
        """Register all posts from a DistributionResult so their platforms are known."""
        for post in result.posts:
            self._platforms[post.tracking_id] = post.platform
            if post.tracking_id not in self._events:
                self._events[post.tracking_id] = []

    def register_distributions(self, results: list[DistributionResult]) -> None:
        """Register all posts from a list of DistributionResult objects."""
        for result in results:
            self.register_distribution(result)

    # ------------------------------------------------------------------
    # Event recording
    # ------------------------------------------------------------------

    def record(self, event: ConversionEvent) -> None:
        """Record a single conversion event."""
        self._events[event.tracking_id].append(event)
        if event.tracking_id not in self._platforms:
            self._platforms[event.tracking_id] = event.platform
        logger.info(
            "ConversionTracker: %s event on %s (tracking_id=%s, value=%.2f).",
            event.event_type.value,
            event.platform.value,
            event.tracking_id,
            event.value,
        )

    def record_many(self, events: list[ConversionEvent]) -> None:
        """Record a batch of conversion events."""
        for event in events:
            self.record(event)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def events_for(self, tracking_id: str) -> list[ConversionEvent]:
        """Return all events for a given tracking ID."""
        return list(self._events.get(tracking_id, []))

    def all_events(self) -> list[ConversionEvent]:
        """Return every recorded event across all tracking IDs."""
        events: list[ConversionEvent] = []
        for evts in self._events.values():
            events.extend(evts)
        return events

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def summarize(self, tracking_id: str) -> ConversionSummary:
        """Aggregate all events for *tracking_id* into a ConversionSummary."""
        platform = self._platforms.get(tracking_id, DistributionPlatform.REDDIT)
        summary = ConversionSummary(tracking_id=tracking_id, platform=platform)
        for event in self._events.get(tracking_id, []):
            if event.event_type == ConversionEventType.CLICK:
                summary.clicks += 1
            elif event.event_type == ConversionEventType.SIGNUP:
                summary.signups += 1
            elif event.event_type == ConversionEventType.REPLY:
                summary.replies += 1
            elif event.event_type == ConversionEventType.PAYMENT:
                summary.payments += 1
                summary.total_revenue += event.value
        return summary

    def summarize_all(self) -> list[ConversionSummary]:
        """Return a ConversionSummary for every registered tracking ID."""
        return [self.summarize(tid) for tid in self._platforms]

    def total_revenue(self) -> float:
        """Return the sum of all payment event values."""
        return sum(
            event.value
            for event in self.all_events()
            if event.event_type == ConversionEventType.PAYMENT
        )
