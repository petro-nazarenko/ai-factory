"""Tests for the Idea Generator (dry-run / mock mode)."""

import pytest

from src.idea_generator import IdeaGenerator
from src.models import PainSignal, SignalSource


def _signal(**overrides) -> PainSignal:
    defaults = dict(
        source=SignalSource.MOCK,
        who_is_complaining="E-commerce store owner",
        what_they_want="Automated competitor price tracking",
        current_workaround="Checks 3 competitor sites manually every morning",
        score=8.0,
    )
    defaults.update(overrides)
    return PainSignal(**defaults)


@pytest.mark.asyncio
class TestIdeaGenerator:
    async def test_generate_returns_ideas(self):
        gen = IdeaGenerator(dry_run=True)
        ideas = await gen.generate(_signal(), n=2)
        assert len(ideas) == 2
        for idea in ideas:
            assert idea.problem
            assert idea.target_user
            assert idea.solution
            assert idea.why_now
            assert idea.existing_spend_behavior
            assert idea.signal is not None

    async def test_generate_n_capped_to_mock_data(self):
        """Mock data has 3 entries; requesting more should return at most 3."""
        gen = IdeaGenerator(dry_run=True)
        ideas = await gen.generate(_signal(), n=5)
        assert len(ideas) <= 5

    async def test_generate_one(self):
        gen = IdeaGenerator(dry_run=True)
        ideas = await gen.generate(_signal(), n=1)
        assert len(ideas) == 1

    async def test_generate_all_multiple_signals(self):
        gen = IdeaGenerator(dry_run=True)
        signals = [_signal(score=float(i)) for i in range(7, 10)]
        ideas = await gen.generate_all(signals, n=1)
        # Should have one idea per signal
        assert len(ideas) == len(signals)

    async def test_idea_signal_reference(self):
        """Each idea should reference its originating signal."""
        gen = IdeaGenerator(dry_run=True)
        signal = _signal(what_they_want="Track competitor prices")
        ideas = await gen.generate(signal, n=1)
        assert ideas[0].signal.what_they_want == "Track competitor prices"

    async def test_empty_signal_list(self):
        gen = IdeaGenerator(dry_run=True)
        ideas = await gen.generate_all([])
        assert ideas == []
