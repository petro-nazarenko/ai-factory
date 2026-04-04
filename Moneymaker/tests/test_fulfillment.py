"""Tests for the ManualFulfillment layer (Step 2)."""

import pytest

from src.fulfillment import ManualFulfillment, _mock_fulfill
from src.models import FilterResult, FulfillmentStatus, Idea, MVPPlan, PainSignal, SignalSource


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_signal() -> PainSignal:
    return PainSignal(
        source=SignalSource.MOCK,
        who_is_complaining="Freelancer",
        what_they_want="Auto-format proposals",
        current_workaround="Manual copy-paste",
        score=7.5,
    )


def make_idea(signal: PainSignal | None = None) -> Idea:
    if signal is None:
        signal = make_signal()
    return Idea(
        problem="Freelancers spend 45 min formatting proposals",
        target_user="Freelance copywriter",
        solution="One-click proposal formatter",
        why_now="LLMs make text transformation cheap",
        existing_spend_behavior="Already pays $30/mo for Bonsai",
        signal=signal,
    )


def make_filter_result() -> FilterResult:
    return FilterResult(
        idea=make_idea(),
        passed=True,
        score=7.8,
        has_existing_spending=8.0,
        has_clear_buyer=8.5,
        mvp_feasible_24h=8.0,
        sells_without_brand=7.5,
    )


def make_plan(fmt: str = "landing_page") -> MVPPlan:
    fr = make_filter_result()
    return MVPPlan(
        idea=fr.idea,
        filter_result=fr,
        format=fmt,
        title="ProposalAI",
        tagline="Turn briefs into proposals in one click",
        revenue_model="Monthly SaaS subscription",
        price_point="$49/mo",
        estimated_build_time="2–4 hours",
        validation_steps=["Post in r/freelance", "DM 20 users"],
        tech_stack=["Next.js", "Stripe"],
        template="<html>…</html>",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMockFulfill:
    def test_returns_output_and_notes(self):
        plan = make_plan("landing_page")
        raw = _mock_fulfill(plan)
        assert "output" in raw
        assert "notes" in raw
        assert len(raw["output"]) > 10

    def test_title_substituted_in_output(self):
        plan = make_plan("landing_page")
        raw = _mock_fulfill(plan)
        assert plan.title in raw["output"]

    def test_all_formats_covered(self):
        for fmt in ("landing_page", "telegram_bot", "google_form_manual", "api_wrapper"):
            plan = make_plan(fmt)
            raw = _mock_fulfill(plan)
            assert raw["output"]


@pytest.mark.asyncio
class TestManualFulfillment:
    async def test_dry_run_returns_simulated_result(self):
        fulf = ManualFulfillment(dry_run=True)
        plan = make_plan()
        result = await fulf.fulfill(plan)
        assert result.simulated is True
        assert result.status == FulfillmentStatus.SIMULATED
        assert result.output

    async def test_fulfill_all_returns_one_per_plan(self):
        fulf = ManualFulfillment(dry_run=True)
        plans = [make_plan(fmt) for fmt in ("landing_page", "telegram_bot")]
        results = await fulf.fulfill_all(plans)
        assert len(results) == 2

    async def test_result_contains_plan(self):
        fulf = ManualFulfillment(dry_run=True)
        plan = make_plan()
        result = await fulf.fulfill(plan)
        assert result.plan is plan

    async def test_all_formats_produce_output(self):
        fulf = ManualFulfillment(dry_run=True)
        for fmt in ("landing_page", "telegram_bot", "google_form_manual", "api_wrapper"):
            plan = make_plan(fmt)
            result = await fulf.fulfill(plan)
            assert result.output, f"No output for format '{fmt}'"

    async def test_no_api_key_falls_back_to_mock(self):
        """Without an API key, live mode should fall back to simulated output."""
        from unittest.mock import patch
        from src.config import settings

        fulf = ManualFulfillment(dry_run=False)
        plan = make_plan()
        with patch.object(settings, "anthropic_api_key", ""):
            result = await fulf.fulfill(plan)
        assert result.simulated is True
        assert result.output
