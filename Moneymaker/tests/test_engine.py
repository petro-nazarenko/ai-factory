"""Tests for the full Engine pipeline (dry-run mode)."""

import pytest

from src.engine import Engine
from src.models import MVPPlan, PainSignal


@pytest.mark.asyncio
class TestEngine:
    async def test_mine_signals_dry_run(self):
        engine = Engine(dry_run=True, signal_limit=6)
        signals = await engine.mine_signals()
        assert len(signals) >= 1
        assert len(signals) <= 6
        for s in signals:
            assert isinstance(s, PainSignal)
            assert s.score >= 0.0

    async def test_signals_sorted_by_score(self):
        engine = Engine(dry_run=True, signal_limit=20)
        signals = await engine.mine_signals()
        scores = [s.score for s in signals]
        assert scores == sorted(scores, reverse=True)

    async def test_generate_ideas(self):
        engine = Engine(dry_run=True, signal_limit=3)
        signals = await engine.mine_signals()
        ideas = await engine.generate_ideas(signals)
        assert len(ideas) >= len(signals)  # at least one idea per signal

    async def test_filter_ideas(self):
        engine = Engine(dry_run=True, signal_limit=3)
        signals = await engine.mine_signals()
        ideas = await engine.generate_ideas(signals)
        filtered = await engine.filter_ideas(ideas)
        # All returned results must have passed=True
        for fr in filtered:
            assert fr.passed is True

    async def test_build_mvps(self):
        engine = Engine(dry_run=True, signal_limit=3)
        signals = await engine.mine_signals()
        ideas = await engine.generate_ideas(signals)
        filtered = await engine.filter_ideas(ideas)
        plans = await engine.build_mvps(filtered)
        for plan in plans:
            assert isinstance(plan, MVPPlan)
            assert plan.title
            assert plan.tagline
            assert plan.format in ("landing_page", "telegram_bot", "google_form_manual", "api_wrapper")
            assert plan.template  # template should be populated

    async def test_full_run(self):
        """End-to-end pipeline in dry-run mode should produce at least one MVP plan."""
        engine = Engine(dry_run=True, signal_limit=4)
        plans = await engine.run()
        assert len(plans) >= 1
        for plan in plans:
            assert isinstance(plan, MVPPlan)

    async def test_single_source(self):
        engine = Engine(sources=["reddit"], dry_run=True, signal_limit=5)
        signals = await engine.mine_signals()
        assert len(signals) >= 1

    async def test_unknown_source_skipped(self):
        engine = Engine(sources=["reddit", "unknown_source"], dry_run=True, signal_limit=5)
        # Should not raise; unknown source is silently skipped
        signals = await engine.mine_signals()
        assert isinstance(signals, list)

    async def test_empty_source_list(self):
        engine = Engine(sources=[], dry_run=True, signal_limit=5)
        signals = await engine.mine_signals()
        assert signals == []
