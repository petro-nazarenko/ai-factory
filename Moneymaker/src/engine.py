"""Engine — main orchestrator for the 4-layer MVP Idea Engine pipeline.

Usage
-----
    engine = Engine(sources=["reddit", "producthunt"], signal_limit=20, dry_run=True)
    signals  = await engine.mine_signals()
    ideas    = await engine.generate_ideas(signals)
    filtered = await engine.filter_ideas(ideas)
    plans    = await engine.build_mvps(filtered)

    # Optional downstream layers
    fulfilled    = await engine.fulfill_mvps(plans)
    distributed  = await engine.distribute_mvps(plans)
    tracker      = engine.conversion_tracker
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from src.conversion_tracker import ConversionTracker
from src.distributor import Distributor
from src.fulfillment import ManualFulfillment
from src.idea_generator import IdeaGenerator
from src.models import FilterResult, FulfillmentResult, DistributionResult, Idea, MVPPlan, PainSignal
from src.money_filter import MoneyFilter
from src.mvp_builder import MVPBuilder
from src.signal_miner.base import BaseSignalMiner
from src.signal_miner.idea_seekers import IdeaSeekersSignalMiner
from src.signal_miner.indiehackers import IndieHackersSignalMiner
from src.signal_miner.jobboards import JobBoardsSignalMiner
from src.signal_miner.producthunt import ProductHuntSignalMiner
from src.signal_miner.reddit import RedditSignalMiner

logger = logging.getLogger(__name__)

SourceName = Literal["reddit", "producthunt", "indiehackers", "jobboards", "idea_seekers"]

_MINER_MAP: dict[str, type[BaseSignalMiner]] = {
    "reddit": RedditSignalMiner,
    "producthunt": ProductHuntSignalMiner,
    "indiehackers": IndieHackersSignalMiner,
    "jobboards": JobBoardsSignalMiner,
    "idea_seekers": IdeaSeekersSignalMiner,
}


class Engine:
    """
    Orchestrates all four pipeline layers.

    Parameters
    ----------
    sources:
        Which signal sources to activate.  Defaults to all four.
    signal_limit:
        Total maximum number of pain signals to collect across all sources.
    dry_run:
        When *True*, every layer uses mock/heuristic data — no external API
        calls are made.  Ideal for local development and testing.
    """

    def __init__(
        self,
        sources: list[str] | None = None,
        signal_limit: int = 10,
        dry_run: bool = False,
        platforms: list[str] | None = None,
        weights: dict | None = None,
    ) -> None:
        self.sources = sources if sources is not None else list(_MINER_MAP.keys())
        self.signal_limit = signal_limit
        self.dry_run = dry_run
        self._weights: dict = weights or {}

        format_weights = self._weights.get("format_weights", {})
        self._idea_generator = IdeaGenerator(dry_run=dry_run)
        self._money_filter = MoneyFilter(dry_run=dry_run)
        self._mvp_builder = MVPBuilder(dry_run=dry_run, format_weights=format_weights)
        self._fulfillment = ManualFulfillment(dry_run=dry_run)
        self._distributor = Distributor(dry_run=dry_run, platforms=platforms)
        self.conversion_tracker = ConversionTracker()

    # ------------------------------------------------------------------
    # Layer 1 — Signal Miner
    # ------------------------------------------------------------------

    async def mine_signals(self) -> list[PainSignal]:
        """Run all configured signal miners concurrently, weighted by source performance."""
        source_weights = self._weights.get("source_weights", {})
        total_weight = sum(source_weights.get(s, 1.0) for s in self.sources) or len(self.sources)

        miners: list[BaseSignalMiner] = []
        for source in self.sources:
            miner_cls = _MINER_MAP.get(source)
            if miner_cls is None:
                logger.warning("Unknown source '%s' — skipping.", source)
                continue
            w = source_weights.get(source, 1.0)
            per_source = max(1, round(self.signal_limit * w / total_weight))
            miners.append(miner_cls(limit=per_source, dry_run=self.dry_run))

        results = await asyncio.gather(*(m.mine() for m in miners), return_exceptions=True)

        signals: list[PainSignal] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.error("Signal miner error: %s", result)
            else:
                signals.extend(result)

        # Sort by score descending, cap at global limit
        signals.sort(key=lambda s: s.score, reverse=True)
        logger.info("Engine: collected %d signals total.", len(signals))
        return signals[: self.signal_limit]

    # ------------------------------------------------------------------
    # Layer 2 — Idea Generator
    # ------------------------------------------------------------------

    async def generate_ideas(self, signals: list[PainSignal]) -> list[Idea]:
        """Generate product ideas from a list of pain signals."""
        ideas = await self._idea_generator.generate_all(signals)
        logger.info("Engine: generated %d ideas.", len(ideas))
        return ideas

    # ------------------------------------------------------------------
    # Layer 3 — Money Filter
    # ------------------------------------------------------------------

    async def evaluate_ideas(self, ideas: list[Idea]) -> list[FilterResult]:
        """Evaluate all ideas and return ALL results (passed and rejected)."""
        results: list[FilterResult] = list(
            await asyncio.gather(*(self._money_filter.evaluate(idea) for idea in ideas))
        )
        logger.info("Engine: evaluated %d ideas.", len(results))
        return results

    async def filter_ideas(self, ideas: list[Idea]) -> list[FilterResult]:
        """Filter ideas by monetization criteria; returns only passed results."""
        passed = await self._money_filter.filter_all(ideas)
        logger.info("Engine: %d ideas passed money filter.", len(passed))
        return passed

    # ------------------------------------------------------------------
    # Layer 4 — MVP Builder
    # ------------------------------------------------------------------

    async def build_mvps(self, filter_results: list[FilterResult]) -> list[MVPPlan]:
        """Build MVP plans for all passed filter results."""
        plans = await self._mvp_builder.build_all(filter_results)
        logger.info("Engine: built %d MVP plans.", len(plans))
        return plans

    # ------------------------------------------------------------------
    # Layer 5 — Manual Fulfillment
    # ------------------------------------------------------------------

    async def fulfill_mvps(self, plans: list[MVPPlan]) -> list[FulfillmentResult]:
        """Execute (or simulate) the MVP service for each plan."""
        results = await self._fulfillment.fulfill_all(plans)
        logger.info("Engine: fulfilled %d MVP plans.", len(results))
        return results

    # ------------------------------------------------------------------
    # Layer 6 — Distribution Injection
    # ------------------------------------------------------------------

    async def distribute_mvps(self, plans: list[MVPPlan]) -> list[DistributionResult]:
        """Generate and publish distribution posts for each plan."""
        results = await self._distributor.distribute_all(plans)
        self.conversion_tracker.register_distributions(results)
        logger.info("Engine: distributed %d MVP plans.", len(results))
        return results

    # ------------------------------------------------------------------
    # Convenience — run entire pipeline in one call
    # ------------------------------------------------------------------

    async def run(self) -> list[MVPPlan]:
        """Execute the complete 4-layer pipeline and return MVP plans."""
        signals = await self.mine_signals()
        ideas = await self.generate_ideas(signals)
        filtered = await self.filter_ideas(ideas)
        plans = await self.build_mvps(filtered)
        return plans
