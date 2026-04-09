"""Tests for the ConversionTracker layer (Step 4)."""

from datetime import datetime, timezone

import pytest

from src.conversion_tracker import ConversionTracker
from src.models import (
    ConversionEvent,
    ConversionEventType,
    ConversionSummary,
    DistributionPlatform,
    DistributionPost,
    DistributionResult,
    FilterResult,
    Idea,
    MVPPlan,
    PainSignal,
    SignalSource,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_plan() -> MVPPlan:
    signal = PainSignal(
        source=SignalSource.MOCK,
        who_is_complaining="Freelancer",
        what_they_want="Auto-format proposals",
        current_workaround="Manual copy-paste",
        score=7.5,
    )
    idea = Idea(
        problem="Freelancers spend 45 min formatting proposals",
        target_user="Freelance copywriter",
        solution="One-click proposal formatter",
        why_now="LLMs make text transformation cheap",
        existing_spend_behavior="Already pays $30/mo for Bonsai",
        signal=signal,
    )
    fr = FilterResult(
        idea=idea,
        passed=True,
        score=7.8,
        has_existing_spending=8.0,
        has_clear_buyer=8.5,
        mvp_feasible_24h=8.0,
        sells_without_brand=7.5,
    )
    return MVPPlan(
        idea=idea,
        filter_result=fr,
        format="landing_page",
        title="ProposalAI",
        tagline="Turn briefs into proposals in one click",
        revenue_model="Monthly SaaS subscription",
        price_point="$49/mo",
        estimated_build_time="2–4 hours",
    )


def make_distribution_result(tracking_id: str = "abc123") -> DistributionResult:
    plan = make_plan()
    post = DistributionPost(
        platform=DistributionPlatform.REDDIT,
        tracking_id=tracking_id,
        body="Problem → solution → demo → CTA",
        cta="Sign up now",
    )
    return DistributionResult(plan=plan, posts=[post])


def make_event(
    tracking_id: str = "abc123",
    event_type: ConversionEventType = ConversionEventType.CLICK,
    platform: DistributionPlatform = DistributionPlatform.REDDIT,
    value: float = 0.0,
) -> ConversionEvent:
    return ConversionEvent(
        tracking_id=tracking_id,
        event_type=event_type,
        platform=platform,
        value=value,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConversionTrackerRecord:
    def test_record_single_click(self):
        tracker = ConversionTracker()
        event = make_event(event_type=ConversionEventType.CLICK)
        tracker.record(event)
        assert len(tracker.events_for("abc123")) == 1

    def test_record_many_events(self):
        tracker = ConversionTracker()
        events = [make_event() for _ in range(5)]
        tracker.record_many(events)
        assert len(tracker.all_events()) == 5

    def test_events_for_unknown_id_returns_empty(self):
        tracker = ConversionTracker()
        assert tracker.events_for("nonexistent") == []

    def test_all_events_spans_multiple_ids(self):
        tracker = ConversionTracker()
        tracker.record(make_event(tracking_id="id1"))
        tracker.record(make_event(tracking_id="id2"))
        assert len(tracker.all_events()) == 2


class TestConversionTrackerRegister:
    def test_register_distribution(self):
        tracker = ConversionTracker()
        dist_result = make_distribution_result("tid1")
        tracker.register_distribution(dist_result)
        # Should be in the platforms map
        summary = tracker.summarize("tid1")
        assert summary.tracking_id == "tid1"
        assert summary.platform == DistributionPlatform.REDDIT

    def test_register_distributions(self):
        tracker = ConversionTracker()
        results = [
            make_distribution_result("tid1"),
            make_distribution_result("tid2"),
        ]
        tracker.register_distributions(results)
        summaries = tracker.summarize_all()
        ids = {s.tracking_id for s in summaries}
        assert {"tid1", "tid2"} <= ids


class TestConversionTrackerSummarize:
    def test_click_counted(self):
        tracker = ConversionTracker()
        tracker.record(make_event(event_type=ConversionEventType.CLICK))
        summary = tracker.summarize("abc123")
        assert summary.clicks == 1
        assert summary.signups == 0

    def test_signup_counted(self):
        tracker = ConversionTracker()
        tracker.record(make_event(event_type=ConversionEventType.SIGNUP))
        summary = tracker.summarize("abc123")
        assert summary.signups == 1

    def test_reply_counted(self):
        tracker = ConversionTracker()
        tracker.record(make_event(event_type=ConversionEventType.REPLY))
        summary = tracker.summarize("abc123")
        assert summary.replies == 1

    def test_payment_counted_and_revenue_summed(self):
        tracker = ConversionTracker()
        tracker.record(make_event(event_type=ConversionEventType.PAYMENT, value=49.0))
        tracker.record(make_event(event_type=ConversionEventType.PAYMENT, value=49.0))
        summary = tracker.summarize("abc123")
        assert summary.payments == 2
        assert summary.total_revenue == pytest.approx(98.0)

    def test_mixed_events(self):
        tracker = ConversionTracker()
        tracker.record(make_event(event_type=ConversionEventType.CLICK))
        tracker.record(make_event(event_type=ConversionEventType.CLICK))
        tracker.record(make_event(event_type=ConversionEventType.SIGNUP))
        tracker.record(make_event(event_type=ConversionEventType.PAYMENT, value=29.0))
        summary = tracker.summarize("abc123")
        assert summary.clicks == 2
        assert summary.signups == 1
        assert summary.payments == 1
        assert summary.total_revenue == pytest.approx(29.0)

    def test_summarize_all_returns_one_per_tracked_id(self):
        tracker = ConversionTracker()
        tracker.record(make_event(tracking_id="id1", event_type=ConversionEventType.CLICK))
        tracker.record(make_event(tracking_id="id2", event_type=ConversionEventType.CLICK))
        summaries = tracker.summarize_all()
        ids = {s.tracking_id for s in summaries}
        assert "id1" in ids
        assert "id2" in ids

    def test_total_revenue(self):
        tracker = ConversionTracker()
        tracker.record(make_event(event_type=ConversionEventType.PAYMENT, value=49.0))
        tracker.record(make_event(event_type=ConversionEventType.PAYMENT, value=99.0))
        tracker.record(make_event(event_type=ConversionEventType.CLICK))
        assert tracker.total_revenue() == pytest.approx(148.0)

    def test_total_revenue_empty(self):
        tracker = ConversionTracker()
        assert tracker.total_revenue() == 0.0

    def test_summary_default_zeroes(self):
        tracker = ConversionTracker()
        tracker.register_distribution(make_distribution_result("new_id"))
        summary = tracker.summarize("new_id")
        assert isinstance(summary, ConversionSummary)
        assert summary.clicks == 0
        assert summary.payments == 0
        assert summary.total_revenue == 0.0
