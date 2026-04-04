"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from src.models import (
    FilterResult,
    Idea,
    MVPPlan,
    PainSignal,
    RejectReason,
    SignalSource,
)


def make_signal(**overrides) -> PainSignal:
    defaults = dict(
        source=SignalSource.MOCK,
        who_is_complaining="Freelancer",
        what_they_want="Auto-format proposals",
        current_workaround="Manual copy-paste",
        score=7.5,
    )
    defaults.update(overrides)
    return PainSignal(**defaults)


def make_idea(signal: PainSignal | None = None, **overrides) -> Idea:
    if signal is None:
        signal = make_signal()
    defaults = dict(
        problem="Freelancers spend 45 min formatting proposals",
        target_user="Freelance copywriter",
        solution="One-click proposal formatter",
        why_now="LLMs make text transformation cheap",
        existing_spend_behavior="Already pays $30/mo for Bonsai",
        signal=signal,
    )
    defaults.update(overrides)
    return Idea(**defaults)


def make_filter_result(passed: bool = True, **overrides) -> FilterResult:
    idea = make_idea()
    defaults = dict(
        idea=idea,
        passed=passed,
        score=7.8,
        has_existing_spending=8.0,
        has_clear_buyer=8.5,
        mvp_feasible_24h=8.0,
        sells_without_brand=7.5,
    )
    defaults.update(overrides)
    return FilterResult(**defaults)


class TestPainSignal:
    def test_valid_creation(self):
        s = make_signal()
        assert s.source == SignalSource.MOCK
        assert s.score == 7.5

    def test_score_clamp_low(self):
        with pytest.raises(ValidationError):
            make_signal(score=-1.0)

    def test_score_clamp_high(self):
        with pytest.raises(ValidationError):
            make_signal(score=11.0)

    def test_defaults(self):
        s = make_signal()
        assert s.source_url == ""
        assert s.raw_text == ""

    def test_all_sources(self):
        for src in SignalSource:
            s = make_signal(source=src)
            assert s.source == src


class TestIdea:
    def test_valid_creation(self):
        idea = make_idea()
        assert idea.target_user == "Freelance copywriter"
        assert idea.signal is not None

    def test_signal_nested(self):
        signal = make_signal(score=9.0)
        idea = make_idea(signal=signal)
        assert idea.signal.score == 9.0

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            Idea(
                problem="A problem",
                target_user="Someone",
                solution="A solution",
                why_now="Now",
                # missing existing_spend_behavior and signal
            )


class TestFilterResult:
    def test_passed(self):
        fr = make_filter_result(passed=True)
        assert fr.passed is True
        assert fr.reject_reason is None

    def test_failed_with_reason(self):
        fr = make_filter_result(
            passed=False,
            score=2.5,
            reject_reason=RejectReason.FUTURE_MARKET,
        )
        assert fr.passed is False
        assert fr.reject_reason == RejectReason.FUTURE_MARKET

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            make_filter_result(score=11.0)

    def test_all_reject_reasons(self):
        for reason in RejectReason:
            fr = make_filter_result(passed=False, score=2.0, reject_reason=reason)
            assert fr.reject_reason == reason


class TestMVPPlan:
    def test_creation(self):
        fr = make_filter_result()
        plan = MVPPlan(
            idea=fr.idea,
            filter_result=fr,
            format="landing_page",
            title="ProposalAI",
            tagline="Turn briefs into proposals in one click",
            revenue_model="Monthly SaaS subscription",
            price_point="$49/mo",
            estimated_build_time="2–4 hours",
            validation_steps=["Post in r/freelance", "DM 20 users"],
            tech_stack=["Next.js", "Stripe"],
        )
        assert plan.format == "landing_page"
        assert plan.price_point == "$49/mo"
        assert len(plan.validation_steps) == 2

    def test_all_formats(self):
        fr = make_filter_result()
        for fmt in ("landing_page", "telegram_bot", "google_form_manual", "api_wrapper"):
            plan = MVPPlan(
                idea=fr.idea,
                filter_result=fr,
                format=fmt,
                title="Test",
                tagline="Test tagline",
                revenue_model="Subscription",
                price_point="$29/mo",
                estimated_build_time="2h",
            )
            assert plan.format == fmt
