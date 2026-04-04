"""Autonomous 24-hour pipeline loop.

Each cycle:
  1. Load learned weights from persistent memory
  2. Mine pain signals (source allocation biased by weights)
  3. Generate + filter ideas
  4. Build MVP plans, pick the highest-scoring one
  5. Deploy a live landing page (Vercel)
  6. Post publicly across distribution channels
  7. Persist all results to SQLite
  8. Recompute weights from history
  9. Sleep until next cycle
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from src.config import settings
from src.deployer import Deployer
from src.engine import Engine
from src.memory import Memory, init_db
from src.weights import compute_weights

logger = logging.getLogger(__name__)


async def _persist_all_ideas(
    memory: Memory,
    run_id: str,
    all_results: list,
    deployed_url_for: dict,
    plans: list | None = None,
) -> None:
    """Save every FilterResult to memory — both passed and rejected."""
    plan_by_result_id = {id(p.filter_result): p for p in (plans or [])}
    for result in all_results:
        plan = plan_by_result_id.get(id(result))
        await memory.save_idea(
            run_id=run_id,
            source=result.idea.signal.source.value,
            problem=result.idea.problem,
            target_user=result.idea.target_user,
            solution=result.idea.solution,
            passed=result.passed,
            score=result.score,
            reject_reason=result.reject_reason.value if result.reject_reason else "",
            mvp_format=plan.format if plan else "",
            deployed_url=deployed_url_for.get(id(result), ""),
        )


async def _cycle(memory: Memory, deployer: Deployer, run_id: str) -> None:
    logger.info("=== Cycle %s started at %s ===", run_id, datetime.now(timezone.utc).isoformat())
    await memory.start_run(run_id)

    # 1. Load weights
    weights = await memory.load_weights()

    # 2. Build weighted source order
    all_sources = ["reddit", "producthunt", "indiehackers", "jobboards"]
    source_weights = weights.get("source_weights", {})
    sources = sorted(all_sources, key=lambda s: source_weights.get(s, 1.0), reverse=True)

    engine = Engine(
        sources=sources,
        signal_limit=settings.loop_signal_limit,
        dry_run=False,
        weights=weights,
    )

    # 3. Pipeline
    signals = await engine.mine_signals()
    ideas = await engine.generate_ideas(signals)
    all_results = await engine.evaluate_ideas(ideas)   # ALL — for memory
    filtered = [r for r in all_results if r.passed]
    plans = await engine.build_mvps(filtered)

    if not plans:
        logger.warning("Cycle %s: no plans produced — skipping deploy/distribute.", run_id)
        await _persist_all_ideas(memory, run_id, all_results, deployed_url_for={})
        await memory.finish_run(
            run_id,
            signals_mined=len(signals),
            ideas_generated=len(ideas),
            ideas_passed=0,
            plans_built=0,
        )
        return

    # 4. Pick best plan by filter score
    best = max(plans, key=lambda p: p.filter_result.score)
    logger.info("Best plan: '%s' (score=%.1f, format=%s)", best.title, best.filter_result.score, best.format)

    # 5. Deploy
    url = await deployer.deploy(best)

    # 6. Persist ALL ideas (passed + rejected) with reject reasons
    deployed_url_for = {id(best.filter_result): url}
    await _persist_all_ideas(memory, run_id, all_results, deployed_url_for, plans)

    # 7. Distribute best plan
    await engine.distribute_mvps([best])

    # 8. Finish run record
    await memory.finish_run(
        run_id,
        signals_mined=len(signals),
        ideas_generated=len(ideas),
        ideas_passed=len(filtered),
        plans_built=len(plans),
        deployed_url=url,
    )

    # 9. Recompute + save weights
    new_weights = await compute_weights(memory)
    await memory.save_weights(new_weights)

    logger.info("=== Cycle %s complete — deployed: %s ===", run_id, url or "(none)")


async def run_loop() -> None:
    """Entry point for the autonomous daemon."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    await init_db()
    memory = Memory()
    deployer = Deployer()
    interval = settings.loop_interval_hours * 3600

    logger.info(
        "Autonomous loop starting — interval=%dh signal_limit=%d",
        settings.loop_interval_hours,
        settings.loop_signal_limit,
    )

    while True:
        run_id = (
            f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            f"-{uuid.uuid4().hex[:6]}"
        )
        try:
            await _cycle(memory, deployer, run_id)
        except Exception:
            logger.exception("Cycle %s failed — will retry next interval.", run_id)

        logger.info("Sleeping %d hours…", settings.loop_interval_hours)
        await asyncio.sleep(interval)
