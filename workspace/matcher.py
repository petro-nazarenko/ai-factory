"""matcher.py — AI Factory STEP 6 (Pipeline 3)

Matches validated ideas (connector.json from a run) against leads (leads.json)
and produces a ranked list of idea ↔ lead pairs with LLM-scored fit.

Matching strategy (two-phase):
  1. Keyword overlap — fast pre-filter (Jaccard, 0–5 scale)
  2. LLM scoring    — nuanced fit_score (0–10) + one-line match_reason

Usage:
    python workspace/matcher.py \
        --runs workspace/runs/ \
        [--run-id run_20260408_031820] \
        [--leads workspace/leads/leads.json] \
        [--output workspace/matches/matches.json] \
        [--min-score 5.0] \
        [--dry-run]

Input files:
    connector.json  — validated ideas (score ≥ 7.0) from a pipeline run
    leads.json      — lead profiles from workspace/leads/

Output:
    matches.json — array of match objects:
    [
      {
        "idea": "SalesAI",
        "lead_company": "PBS",
        "lead_url": "https://news.ycombinator.com/item?id=...",
        "lead_contact": "user@company.com",
        "fit_score": 8.5,
        "match_reason": "PBS hiring SDRs → SalesAI solves SDR assessment",
        "idea_score": 7.9,
        "idea_source_url": "...",
        "idea_posted_date": "..."
      }
    ]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default paths (relative to this file's location — workspace/)
# ---------------------------------------------------------------------------

_DEFAULT_RUNS_DIR = Path(__file__).resolve().parent / "runs"
_DEFAULT_LEADS = Path(__file__).resolve().parent / "leads" / "leads.json"
_DEFAULT_OUTPUT = Path(__file__).resolve().parent / "matches" / "matches.json"
_MIN_SCORE_DEFAULT = 5.0
# Minimum scaled keyword score (0–5 range) required to proceed to LLM scoring.
# 0.3 / 5.0 ≈ 6% Jaccard similarity — filters out pairs with essentially no
# shared vocabulary while keeping any pair with even light topic overlap.
_KW_PREFILTER_THRESHOLD = 0.3

# ---------------------------------------------------------------------------
# Keyword overlap scoring
# ---------------------------------------------------------------------------

_TOKENIZE_RE = re.compile(r"\b[a-z]{3,}\b")

_STOP_WORDS: frozenset[str] = frozenset({
    "the", "and", "for", "this", "that", "are", "with", "have", "from",
    "our", "will", "can", "more", "not", "but", "all", "you", "your",
    "its", "they", "their", "has", "was", "also", "any", "use", "into",
    "who", "what", "when", "where", "how", "why", "which", "than", "create",
    "solution", "spec", "target", "user", "model", "revenue", "monthly",
    "saas", "subscription",
})


def _tokens(text: str) -> set[str]:
    return set(_TOKENIZE_RE.findall(text.lower())) - _STOP_WORDS


def _keyword_score(idea_text: str, lead_pain: str) -> float:
    """Jaccard-like overlap between idea tokens and lead pain tokens.

    Returns a float in [0, 5].
    """
    idea_tokens = _tokens(idea_text)
    pain_tokens = _tokens(lead_pain)
    if not idea_tokens or not pain_tokens:
        return 0.0
    overlap = idea_tokens & pain_tokens
    union = idea_tokens | pain_tokens
    jaccard = len(overlap) / len(union)
    return round(jaccard * 5.0, 2)


# ---------------------------------------------------------------------------
# LLM-based fit scoring
# ---------------------------------------------------------------------------

_SCORE_SYSTEM = (
    "You are a B2B fit scoring engine. "
    "Given an idea and a lead, return ONLY a JSON object: "
    '{"fit_score": <float 0-10>, "match_reason": "<one sentence>"}. '
    "No markdown, no explanation outside the JSON object."
)

_SCORE_PROMPT_TEMPLATE = """\
IDEA:
{idea_text}

LEAD:
Company: {company}
Pain: {pain}

Score how well this idea solves the lead's pain (0=no fit, 10=perfect fit).
Return JSON: {{"fit_score": <float>, "match_reason": "<one sentence why>"}}
"""


def _llm_score(idea: dict, lead: dict, router) -> tuple[float, str]:
    """Use the LLM router to produce (fit_score, match_reason).

    Falls back to (0.0, "") on any error so the pipeline continues.
    """
    prompt = _SCORE_PROMPT_TEMPLATE.format(
        idea_text=idea.get("prompt", idea.get("source_idea", "")),
        company=lead.get("company", "Unknown"),
        pain=lead.get("pain", ""),
    )
    try:
        raw = router.complete("scoring", prompt, system_prompt=_SCORE_SYSTEM)
        # Strip possible markdown fences before JSON parsing
        clean = re.sub(r"```[a-z]*\n?", "", raw).strip()
        data = json.loads(clean)
        score = float(data.get("fit_score", 0.0))
        reason = str(data.get("match_reason", ""))
        return round(min(max(score, 0.0), 10.0), 2), reason
    except Exception as exc:
        logger.warning(
            "LLM scoring failed for '%s' × '%s': %s",
            idea.get("source_idea", "?"),
            lead.get("company", "?"),
            exc,
        )
        return 0.0, ""


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

def match(
    ideas: list[dict],
    leads: list[dict],
    min_score: float = _MIN_SCORE_DEFAULT,
    dry_run: bool = False,
) -> list[dict]:
    """Match each idea against each lead and return ranked match objects.

    Two-phase matching:
    1. Keyword overlap (Jaccard, 0–5) — fast pre-filter; pairs scoring below
       _KW_PREFILTER_THRESHOLD are skipped to save LLM calls.
    2. LLM scoring — precise fit_score (0–10) + match_reason.

    In dry-run mode, the LLM step is skipped; keyword score is scaled to
    0–10 and used directly as fit_score.

    Args:
        ideas:     list of dicts from connector.json
        leads:     list of dicts from leads.json
        min_score: only include matches with fit_score >= min_score
        dry_run:   skip LLM calls (keyword score × 2 used instead)

    Returns:
        List of match dicts sorted by fit_score descending.
    """
    if not dry_run:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from llm_router import router as _llm_router  # noqa: PLC0415
    else:
        _llm_router = None

    results: list[dict] = []

    for idea in ideas:
        idea_text = " ".join(filter(None, [
            idea.get("prompt", ""),
            idea.get("source_text", ""),
            idea.get("source_idea", ""),
        ]))

        for lead in leads:
            pain = lead.get("pain", "")

            # Phase 1 — keyword overlap pre-filter (applied in both modes)
            kw_score = _keyword_score(idea_text, pain)
            if kw_score < _KW_PREFILTER_THRESHOLD:
                continue

            if dry_run:
                # Scale keyword score (0–5) to fit_score (0–10)
                fit_score = round(kw_score * 2.0, 2)
                match_reason = (
                    f"{lead.get('company', 'Lead')} needs "
                    f"{idea.get('source_idea', 'this solution')} "
                    f"(keyword overlap {kw_score:.1f}/5)"
                )
            else:
                fit_score, match_reason = _llm_score(idea, lead, _llm_router)

            if fit_score < min_score:
                continue

            results.append({
                "idea": idea.get("source_idea", ""),
                "lead_company": lead.get("company", "Unknown"),
                "lead_url": lead.get("hn_url", ""),
                "lead_contact": lead.get("contact", ""),
                "fit_score": fit_score,
                "match_reason": match_reason,
                # Extra context for downstream offer generation
                "idea_score": idea.get("score", 0.0),
                "idea_source_url": idea.get("source_url", ""),
                "idea_posted_date": idea.get("posted_date", ""),
            })

    results.sort(key=lambda x: x["fit_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Run discovery
# ---------------------------------------------------------------------------

def _find_connector_json(runs_dir: Path, run_id: str | None) -> Path:
    """Return the connector.json path for a given run_id or the latest run."""
    if not runs_dir.exists():
        raise FileNotFoundError(f"Runs directory not found: {runs_dir}")

    if run_id:
        candidate = runs_dir / run_id / "connector.json"
        if not candidate.exists():
            raise FileNotFoundError(
                f"connector.json not found for run '{run_id}': {candidate}"
            )
        return candidate

    # Find all run dirs that contain a connector.json, sorted newest first.
    # Run IDs follow the format run_YYYYMMDD_HHMMSS so lexicographic sort
    # is equivalent to chronological order.
    candidates = sorted(
        [
            d / "connector.json"
            for d in runs_dir.iterdir()
            if d.is_dir() and (d / "connector.json").exists()
        ],
        key=lambda p: p.parent.name,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"No run with connector.json found in {runs_dir}"
        )
    return candidates[0]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Matcher — idea ↔ lead fit scoring (Pipeline 3, Step 6)"
    )
    parser.add_argument(
        "--runs",
        default=str(_DEFAULT_RUNS_DIR),
        help=f"Path to workspace/runs/ directory (default: {_DEFAULT_RUNS_DIR})",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Specific run ID (default: latest run with connector.json)",
    )
    parser.add_argument(
        "--leads",
        default=str(_DEFAULT_LEADS),
        help=f"Path to leads.json (default: {_DEFAULT_LEADS})",
    )
    parser.add_argument(
        "--output",
        default=str(_DEFAULT_OUTPUT),
        help=f"Output path for matches.json (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=_MIN_SCORE_DEFAULT,
        help=f"Minimum fit_score to include (default: {_MIN_SCORE_DEFAULT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls; use keyword overlap score only",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # --- Load ideas from the selected run ---
    try:
        connector_path = _find_connector_json(Path(args.runs), args.run_id)
    except FileNotFoundError as exc:
        print(f"[MATCHER] [FAIL] {exc}", file=sys.stderr)
        sys.exit(1)

    ideas = json.loads(connector_path.read_text(encoding="utf-8"))
    if not ideas:
        print("[MATCHER] [FAIL] connector.json is empty", file=sys.stderr)
        sys.exit(1)

    run_id = connector_path.parent.name
    print(f"[MATCHER] Run: {run_id} — {len(ideas)} idea(s) loaded")

    # --- Load leads ---
    leads_path = Path(args.leads)
    if not leads_path.exists():
        print(f"[MATCHER] [FAIL] leads.json not found: {leads_path}", file=sys.stderr)
        sys.exit(1)

    leads = json.loads(leads_path.read_text(encoding="utf-8"))
    if not leads:
        print("[MATCHER] [FAIL] leads.json is empty", file=sys.stderr)
        sys.exit(1)

    print(f"[MATCHER] Leads: {len(leads)} loaded from {leads_path}")

    # --- Run matching ---
    print(
        f"[MATCHER] Matching {len(ideas)} idea(s) × {len(leads)} lead(s)"
        f" (dry_run={args.dry_run}, min_score={args.min_score}) ..."
    )
    matches = match(ideas, leads, min_score=args.min_score, dry_run=args.dry_run)
    print(f"[MATCHER] {len(matches)} match(es) with fit_score >= {args.min_score}")

    # --- Write output ---
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(matches, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[MATCHER] Written → {output_path}")

    if not matches:
        print(
            "[MATCHER] [WARN] 0 matches found — "
            "lower --min-score or refresh leads/ideas",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
