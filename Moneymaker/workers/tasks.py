"""Celery task pipeline — each task is one agent in the swarm.

Chain topology
--------------
    mine_signals
        └── generate_ideas
                └── score_and_filter
                        └── build_and_deploy
                                └── distribute_best

Each task receives the serialised output of the previous task as its
first argument (Celery chain convention) and returns JSON-serialisable data.

Async code is executed via asyncio.run() — safe inside a Celery worker process.
"""

from __future__ import annotations

import asyncio
import logging

from celery import chain

from workers.celery_app import app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Serialisation helpers (Pydantic ↔ dict)
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine inside a synchronous Celery task."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Task 1 — Signal Miner Agent
# ---------------------------------------------------------------------------

@app.task(
    name="mine_signals",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def mine_signals(self, sources: list[str] | None = None, limit: int = 40) -> list[dict]:
    """Mine pain signals from all configured sources. Returns list of PainSignal dicts."""
    from src.signal_miner.reddit import RedditSignalMiner
    from src.signal_miner.producthunt import ProductHuntSignalMiner
    from src.signal_miner.indiehackers import IndieHackersSignalMiner
    from src.signal_miner.jobboards import JobBoardsSignalMiner

    _MINERS = {
        "reddit": RedditSignalMiner,
        "producthunt": ProductHuntSignalMiner,
        "indiehackers": IndieHackersSignalMiner,
        "jobboards": JobBoardsSignalMiner,
    }

    active = sources or list(_MINERS.keys())

    async def _mine() -> list[dict]:
        per = max(1, limit // len(active))
        miners = [_MINERS[s](limit=per) for s in active if s in _MINERS]
        results = await asyncio.gather(*[m.mine() for m in miners], return_exceptions=True)
        signals = []
        for r in results:
            if isinstance(r, BaseException):
                logger.error("Miner error: %s", r)
            else:
                signals.extend(r)
        signals.sort(key=lambda s: s.score, reverse=True)
        return [s.model_dump() for s in signals[:limit]]

    try:
        return _run(_mine())
    except Exception as exc:
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 2 — Idea Generator Agent
# ---------------------------------------------------------------------------

@app.task(name="generate_ideas", bind=True, max_retries=3, default_retry_delay=60)
def generate_ideas(self, signals: list[dict]) -> list[dict]:
    """Convert pain signals into product ideas. Returns list of Idea dicts."""
    from src.models import PainSignal
    from src.idea_generator import IdeaGenerator

    async def _generate() -> list[dict]:
        pain_signals = [PainSignal(**s) for s in signals]
        gen = IdeaGenerator()
        ideas = await gen.generate_all(pain_signals)
        return [i.model_dump() for i in ideas]

    try:
        return _run(_generate())
    except Exception as exc:
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 3 — Scoring Agent (Money Filter)
# ---------------------------------------------------------------------------

@app.task(name="score_and_filter", bind=True, max_retries=3, default_retry_delay=60)
def score_and_filter(self, ideas: list[dict]) -> list[dict]:
    """Score and filter ideas. Returns only passed FilterResult dicts."""
    from src.models import Idea
    from src.money_filter import MoneyFilter

    async def _score() -> list[dict]:
        idea_objects = [Idea(**i) for i in ideas]
        filt = MoneyFilter()
        passed = await filt.filter_all(idea_objects)
        return [r.model_dump() for r in passed]

    try:
        return _run(_score())
    except Exception as exc:
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 4 — MVP Builder + Deploy Agent
# ---------------------------------------------------------------------------

@app.task(name="build_and_deploy", bind=True, max_retries=2, default_retry_delay=120)
def build_and_deploy(self, filter_results: list[dict]) -> dict:
    """Build MVP plans, pick the best one, deploy it. Returns plan dict + url."""
    from src.models import FilterResult
    from src.mvp_builder import MVPBuilder
    from src.deployer import Deployer

    async def _build() -> dict:
        results = [FilterResult(**r) for r in filter_results]
        builder = MVPBuilder()
        plans = await builder.build_all(results)
        if not plans:
            return {}
        best = max(plans, key=lambda p: p.filter_result.score)
        url = await Deployer().deploy(best)
        return {**best.model_dump(), "deployed_url": url}

    try:
        return _run(_build())
    except Exception as exc:
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 5 — Distribution Agent
# ---------------------------------------------------------------------------

@app.task(name="distribute_best", bind=True, max_retries=2, default_retry_delay=60)
def distribute_best(self, plan_with_url: dict) -> list[dict]:
    """Post the best plan across distribution channels. Returns DistributionResult dicts."""
    from src.models import MVPPlan
    from src.distributor import Distributor

    if not plan_with_url:
        logger.warning("distribute_best: no plan received — skipping.")
        return []

    async def _distribute() -> list[dict]:
        plan = MVPPlan(**plan_with_url)
        dist = Distributor()
        results = await dist.distribute_all([plan])
        return [r.model_dump() for r in results]

    try:
        return _run(_distribute())
    except Exception as exc:
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 6 — Learning Agent
# ---------------------------------------------------------------------------

@app.task(name="update_weights_task")
def update_weights_task(idea_id: int, metrics: dict) -> dict:
    """Compute reward and update feature weights in Postgres."""
    from core.reward import compute_reward, update_weights, idea_features

    async def _learn() -> dict:
        from infra.db import get_session
        from core.schema import IdeaRecord, WeightRecord
        from sqlalchemy import select

        reward = compute_reward(metrics)

        async with get_session() as session:
            idea = await session.get(IdeaRecord, idea_id)
            if idea is None:
                return {"error": f"idea {idea_id} not found"}

            feats = idea_features(
                source=idea.source,
                mvp_format=idea.mvp_format,
                target_user=idea.target_user,
            )

            # Load current weights
            rows = await session.execute(select(WeightRecord))
            current = {r.feature: r.weight for r in rows.scalars()}

            # Update
            new_weights = update_weights(feats, reward, current)

            # Upsert
            for feature, weight in new_weights.items():
                existing = await session.get(WeightRecord, feature)
                if existing:
                    existing.weight = weight
                else:
                    session.add(WeightRecord(feature=feature, weight=weight))

            await session.commit()

        logger.info("Weights updated — reward=%.2f, idea=%d", reward, idea_id)
        return {"reward": reward, "weights_updated": len(new_weights)}

    return _run(_learn())


# ---------------------------------------------------------------------------
# Orchestrator — fires the full chain
# ---------------------------------------------------------------------------

@app.task(name="trigger_cycle")
def trigger_cycle(
    sources: list[str] | None = None,
    limit: int = 40,
) -> str:
    """Celery-beat entry point — fires the full agent chain and returns the chain task ID."""
    result = run_cycle(sources=sources, limit=limit)
    logger.info("Cycle triggered — chain id=%s", result.id)
    return str(result.id)


def run_cycle(
    sources: list[str] | None = None,
    limit: int = 40,
) -> object:
    """Launch the full agent pipeline as a Celery chain.

    Returns the AsyncResult of the last task.
    """
    pipeline = chain(
        mine_signals.s(sources=sources, limit=limit),
        generate_ideas.s(),
        score_and_filter.s(),
        build_and_deploy.s(),
        distribute_best.s(),
    )
    return pipeline.apply_async()
