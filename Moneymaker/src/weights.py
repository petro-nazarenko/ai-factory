"""Weight learner — derives performance weights from historical memory.

Weights shape the next cycle:
  source_weights  — allocate more signals from sources with higher pass rates
  format_weights  — bias MVP format selection toward formats with more revenue
"""

from __future__ import annotations

import logging
from collections import defaultdict

from src.memory import Memory

logger = logging.getLogger(__name__)


async def compute_weights(memory: Memory) -> dict:
    """Read historical idea stats and return updated weights dict."""
    ideas = await memory.idea_stats(last_n_runs=30)
    revenue_by_format = await memory.revenue_by_format(last_n_runs=30)
    reject_stats = await memory.reject_reason_stats(last_n_runs=30)

    # Log rejection distribution per source — useful for tuning signal miners
    for source, reasons in reject_stats.items():
        total_rejected = sum(reasons.values())
        breakdown = ", ".join(f"{r}={c}" for r, c in sorted(reasons.items(), key=lambda x: -x[1]))
        logger.info("Rejection stats [%s]: %d rejected — %s", source, total_rejected, breakdown)

    # --- source weights (based on pass rate) ---
    source_totals: dict[str, int] = defaultdict(int)
    source_passed: dict[str, int] = defaultdict(int)
    for idea in ideas:
        src = idea["source"]
        source_totals[src] += 1
        if idea["passed"]:
            source_passed[src] += 1

    source_rates = {
        src: source_passed[src] / source_totals[src]
        for src in source_totals
        if source_totals[src] >= 3  # need at least 3 samples
    }
    source_weights = _normalize(source_rates)

    # --- format weights (based on revenue; fall back to deployment count) ---
    format_deployments: dict[str, int] = defaultdict(int)
    for idea in ideas:
        if idea["passed"] and idea["mvp_format"]:
            format_deployments[idea["mvp_format"]] += 1

    if revenue_by_format:
        # Use revenue per deployment as signal
        format_rates = {
            fmt: revenue_by_format.get(fmt, 0.0) / max(1, format_deployments[fmt])
            for fmt in format_deployments
        }
    else:
        # Before any revenue data, weight by deployment success rate
        format_rates = {
            fmt: count / max(1, sum(format_deployments.values()))
            for fmt, count in format_deployments.items()
        }

    format_weights = _normalize(format_rates) if format_rates else {}

    weights = {
        "source_weights": source_weights,
        "format_weights": format_weights,
        "reject_stats": reject_stats,   # read-only analytics, not used for scoring
    }
    logger.info(
        "Weights updated — sources: %s | formats: %s",
        source_weights,
        format_weights,
    )
    return weights


def _normalize(rates: dict[str, float]) -> dict[str, float]:
    """Normalize a dict of rates so the mean == 1.0."""
    if not rates:
        return {}
    mean = sum(rates.values()) / len(rates)
    if mean == 0:
        return {k: 1.0 for k in rates}
    return {k: round(v / mean, 3) for k, v in rates.items()}
