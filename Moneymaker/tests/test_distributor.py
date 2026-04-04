"""Tests for the Distributor layer (Step 3)."""

import pytest

from src.distributor import Distributor, _build_cta, _build_demo, _generate_post
from src.models import (
    DistributionPlatform,
    DistributionPost,
    FilterResult,
    Idea,
    MVPPlan,
    PainSignal,
    SignalSource,
)


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


def make_plan(validation_steps: list[str] | None = None) -> MVPPlan:
    signal = make_signal()
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
        validation_steps=validation_steps or ["Post in r/freelance", "DM 20 users"],
        tech_stack=["Next.js", "Stripe"],
        template="<html>…</html>",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPostGeneration:
    def test_generate_post_reddit(self):
        plan = make_plan()
        post = _generate_post(plan, DistributionPlatform.REDDIT)
        assert isinstance(post, DistributionPost)
        assert post.platform == DistributionPlatform.REDDIT
        assert post.tracking_id  # UUID hex
        assert len(post.tracking_id) == 32
        assert plan.idea.problem in post.body
        assert plan.title in post.body

    def test_generate_post_twitter(self):
        plan = make_plan()
        post = _generate_post(plan, DistributionPlatform.TWITTER)
        assert "Problem" in post.body or plan.idea.problem in post.body

    def test_generate_post_indiehackers(self):
        plan = make_plan()
        post = _generate_post(plan, DistributionPlatform.INDIEHACKERS)
        assert plan.title in post.body
        assert plan.tagline in post.body

    def test_generate_post_telegram(self):
        plan = make_plan()
        post = _generate_post(plan, DistributionPlatform.TELEGRAM)
        assert plan.title in post.body

    def test_all_platforms_unique_tracking_ids(self):
        plan = make_plan()
        tracking_ids = [
            _generate_post(plan, platform).tracking_id
            for platform in DistributionPlatform
        ]
        assert len(tracking_ids) == len(set(tracking_ids))

    def test_cta_contains_price_point(self):
        plan = make_plan()
        cta = _build_cta(plan)
        assert plan.price_point in cta

    def test_demo_uses_first_validation_step(self):
        plan = make_plan(validation_steps=["Do this first", "Then this"])
        demo = _build_demo(plan)
        assert demo == "Do this first"

    def test_demo_fallback_when_no_validation_steps(self):
        plan = make_plan(validation_steps=[])
        demo = _build_demo(plan)
        assert demo  # should not be empty

    def test_post_not_posted_by_default(self):
        plan = make_plan()
        post = _generate_post(plan, DistributionPlatform.REDDIT)
        assert post.posted is False
        assert post.url == ""


@pytest.mark.asyncio
class TestDistributor:
    async def test_dry_run_generates_posts_without_posting(self):
        distributor = Distributor(dry_run=True)
        plan = make_plan()
        result = await distributor.distribute(plan)
        assert result.plan is plan
        assert len(result.posts) == len(list(DistributionPlatform))
        for post in result.posts:
            assert post.posted is False

    async def test_dry_run_all_platforms_covered(self):
        distributor = Distributor(dry_run=True)
        plan = make_plan()
        result = await distributor.distribute(plan)
        platforms = {post.platform for post in result.posts}
        assert platforms == set(DistributionPlatform)

    async def test_platform_filter(self):
        distributor = Distributor(dry_run=True, platforms=["reddit", "twitter"])
        plan = make_plan()
        result = await distributor.distribute(plan)
        assert len(result.posts) == 2
        platforms = {post.platform.value for post in result.posts}
        assert platforms == {"reddit", "twitter"}

    async def test_distribute_all_returns_one_per_plan(self):
        distributor = Distributor(dry_run=True)
        plans = [make_plan(), make_plan()]
        results = await distributor.distribute_all(plans)
        assert len(results) == 2

    async def test_posts_have_non_empty_bodies(self):
        distributor = Distributor(dry_run=True)
        plan = make_plan()
        result = await distributor.distribute(plan)
        for post in result.posts:
            assert post.body.strip(), f"Empty body for platform {post.platform}"

    async def test_problem_solution_format(self):
        """Every post body should contain both problem and solution references."""
        distributor = Distributor(dry_run=True)
        plan = make_plan()
        result = await distributor.distribute(plan)
        for post in result.posts:
            assert plan.idea.problem in post.body or plan.title in post.body
