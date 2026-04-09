"""Tests for the Money Filter Engine (heuristic / dry-run mode)."""

import pytest

from src.models import Idea, PainSignal, RejectReason, SignalSource
from src.money_filter import MoneyFilter, _heuristic_score


def _signal(score: float = 7.5) -> PainSignal:
    return PainSignal(
        source=SignalSource.MOCK,
        who_is_complaining="Freelancer",
        what_they_want="Auto-format proposals",
        current_workaround="Manual copy-paste",
        score=score,
    )


def _idea(**overrides) -> Idea:
    defaults = dict(
        problem="Freelancers spend 45 min formatting proposals",
        target_user="Freelance copywriter with 5+ clients",
        solution="One-click proposal formatter landing page",
        why_now="LLMs make text transformation cheap",
        existing_spend_behavior="Already pays $30/mo for Bonsai and Google Workspace subscription",
        signal=_signal(),
    )
    defaults.update(overrides)
    return Idea(**defaults)


class TestHeuristicScore:
    def test_passing_idea(self):
        result = _heuristic_score(_idea())
        assert result["passed"] is True
        assert result["score"] >= 6.5

    def test_future_market_rejected(self):
        idea = _idea(
            problem="This will need a future market when blockchain matures",
            why_now="Future market will eventually grow",
        )
        result = _heuristic_score(idea)
        assert result["passed"] is False
        assert result["reject_reason"] == RejectReason.FUTURE_MARKET.value

    def test_no_budget_users_rejected(self):
        idea = _idea(
            target_user="Students and hobbyists who can't afford anything",
            existing_spend_behavior="No budget users who rely on free tier only",
        )
        result = _heuristic_score(idea)
        assert result["passed"] is False
        assert result["reject_reason"] == RejectReason.NO_BUDGET_USERS.value

    def test_social_only_rejected(self):
        idea = _idea(
            solution="A platform that only valuable at scale via network effect",
            problem="Needs network effects to work, social platform requires community-driven only",
        )
        result = _heuristic_score(idea)
        assert result["passed"] is False
        assert result["reject_reason"] == RejectReason.SOCIAL_ONLY_VALUE.value

    def test_score_in_range(self):
        result = _heuristic_score(_idea())
        assert 0.0 <= result["score"] <= 10.0

    def test_all_criterion_scores_present(self):
        result = _heuristic_score(_idea())
        for key in ("has_existing_spending", "has_clear_buyer", "mvp_feasible_24h", "sells_without_brand"):
            assert key in result
            assert 0.0 <= result[key] <= 10.0


@pytest.mark.asyncio
class TestMoneyFilter:
    async def test_filter_passes_good_idea(self):
        flt = MoneyFilter(dry_run=True)
        idea = _idea()
        result = await flt.evaluate(idea)
        assert result.passed is True
        assert result.score > 0

    async def test_filter_rejects_future_market(self):
        flt = MoneyFilter(dry_run=True)
        idea = _idea(
            problem="Future market will need this when blockchain matures",
            why_now="Emerging market potential",
        )
        result = await flt.evaluate(idea)
        assert result.passed is False
        assert result.reject_reason == RejectReason.FUTURE_MARKET

    async def test_filter_all_returns_only_passed(self):
        flt = MoneyFilter(dry_run=True)
        good = _idea()
        bad = _idea(
            problem="Future market will need this eventually",
            why_now="Future potential market will eventually emerge",
        )
        results = await flt.filter_all([good, bad])
        # At least the good idea should pass
        assert any(r.passed for r in results)
        # All returned results must be passed
        for r in results:
            assert r.passed is True

    async def test_empty_list(self):
        flt = MoneyFilter(dry_run=True)
        results = await flt.filter_all([])
        assert results == []
