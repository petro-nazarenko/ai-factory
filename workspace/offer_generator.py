"""offer_generator.py — AI Factory STEP 7 (Pipeline 3)

Primary flow: reads connector.json from a pipeline run and generates a
personalized cold-outreach offer for each signal whose author is known.
The signal author IS the lead — no external leads database needed.

Legacy flow (--from-matches): reads matches.json (output of matcher.py)
and uses the company/fit_score fields.  Kept for compatibility.

Output: workspace/offers/offer_N.md  (one file per idea, N = 1-indexed rank)

Markdown format per offer (primary flow):
---
idea: "<source_idea>"
recipient: "<source_author>"
source_url: "<url>"
source_platform: "<platform>"
idea_score: <float>
generated_at: "<ISO 8601>"
status: "draft"
---
Subject: <generated subject line>

<body>

Usage:
    python workspace/offer_generator.py                          # latest run
    python workspace/offer_generator.py --run-id run_20260408_031820
    python workspace/offer_generator.py --dry-run
    python workspace/offer_generator.py --min-score 7.0
    python workspace/offer_generator.py --from-matches          # legacy mode
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from run_utils import find_connector_json

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default paths (relative to this file's location — workspace/)
# ---------------------------------------------------------------------------

_DEFAULT_RUNS_DIR = Path(__file__).resolve().parent / "runs"
_DEFAULT_MATCHES_INPUT = Path(__file__).resolve().parent / "matches" / "matches.json"
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "offers"
_DEFAULT_MIN_SCORE = 7.0

# ---------------------------------------------------------------------------
# LLM prompts — primary (connector.json) flow
# ---------------------------------------------------------------------------

_OFFER_SYSTEM = (
    "You are an expert B2B outreach copywriter. "
    "Write concise, personalized cold-outreach messages. "
    "Return ONLY the message body — no markdown fences, no preamble."
)

_OFFER_PROMPT_TEMPLATE = """\
Write a cold outreach message (max 120 words).
Rules: no preamble, no "I hope this finds you well".
Line 1: their exact problem from source_text.
Line 2-3: what the solution does + build time.
CTA: one ask — call or pilot.

Their post: {source_url}
Their pain: {source_text}
Solution: {prompt}
"""

_SUBJECT_PROMPT_TEMPLATE = """\
Write a concise email subject line (max 10 words) for a cold outreach about:
Solution: {prompt}
Their pain: {source_text}
Return ONLY the subject line text, no quotes.
"""

# ---------------------------------------------------------------------------
# Dry-run / fallback templates — primary flow
# ---------------------------------------------------------------------------

_DRY_RUN_BODY_TEMPLATE = """\
{pain_snippet}

We built {idea} specifically to address this — MVP ships in under a week.

Would you be open to a 30-minute call or a 1-week free pilot?
"""

_DRY_RUN_SUBJECT_TEMPLATE = "Quick idea for {idea}"

# ---------------------------------------------------------------------------
# Legacy LLM prompt — matches flow
# ---------------------------------------------------------------------------

_LEGACY_OFFER_SYSTEM = (
    "You are an expert B2B outreach copywriter. "
    "Write concise, personalized cold-outreach messages that reference the "
    "prospect's specific pain, present the solution clearly, and end with a "
    "soft call-to-action (discovery call OR 1-week pilot). "
    "Return ONLY the message body — no subject line, no sign-off, no markdown fences."
)

_LEGACY_OFFER_PROMPT = """\
Write a personalized outreach message for the following lead.

COMPANY: {company}
THEIR PAIN (from their post): {pain}
OUR SOLUTION: {idea}
POST REFERENCE: {lead_url}
CALL-TO-ACTION: Offer a 30-minute discovery call OR a 1-week free pilot.

Requirements:
- Open by referencing their specific post / pain point (show you read it)
- Explain in 1-2 sentences how the solution directly addresses that pain
- Include the post URL naturally (e.g. "I saw your post at <url>")
- End with a clear, low-friction CTA (discovery call or pilot)
- Keep the message under 150 words
- Tone: professional, direct, founder-to-founder
"""

_LEGACY_DRY_RUN_TEMPLATE = """\
Hi {company} team,

I came across your post at {lead_url} and noticed you're dealing with \
{pain_snippet}.

We built {idea} specifically to solve this — it typically takes under a week \
to integrate and shows measurable results from day one.

Would you be open to a 30-minute call to explore if it's a fit, \
or a 1-week free pilot so you can see it in action?

Looking forward to hearing from you.
"""

# ---------------------------------------------------------------------------
# Run discovery (shared with matcher.py logic)
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int = 80) -> str:
    """Truncate *text* to *max_len* characters, appending '…' if cut."""
    return text[:max_len] + "…" if len(text) > max_len else text


def _is_eligible(idea: dict, min_score: float) -> bool:
    """Return True if the idea has a known author and passes the score filter."""
    author = idea.get("source_author", "").strip()
    return bool(author) and author.lower() != "unknown" and idea.get("score", 0.0) >= min_score


# ---------------------------------------------------------------------------
# Primary flow — generate from connector.json
# ---------------------------------------------------------------------------


def _generate_offer_from_idea(idea: dict, router, dry_run: bool) -> tuple[str, str]:
    """Generate (subject, body) for a single connector.json idea entry.

    Falls back to a template on LLM error so the pipeline never produces
    an empty file.
    """
    source_idea = idea.get("source_idea", "our solution")
    source_url = idea.get("source_url", "")
    source_text = idea.get("source_text", "")
    prompt_text = idea.get("prompt", source_idea)

    pain_snippet = source_text[:300] if source_text else "your current challenge"

    if dry_run:
        subject = _DRY_RUN_SUBJECT_TEMPLATE.format(idea=source_idea)
        body = _DRY_RUN_BODY_TEMPLATE.format(
            pain_snippet=_truncate(pain_snippet),
            idea=source_idea,
        ).strip()
        return subject, body

    body_prompt = _OFFER_PROMPT_TEMPLATE.format(
        source_url=source_url or "(no url)",
        source_text=pain_snippet,
        prompt=prompt_text,
    )
    subject_prompt = _SUBJECT_PROMPT_TEMPLATE.format(
        prompt=prompt_text,
        source_text=pain_snippet[:150],
    )

    try:
        body = router.complete("generation", body_prompt, system_prompt=_OFFER_SYSTEM).strip()
    except Exception as exc:
        logger.warning("LLM body generation failed for '%s': %s", source_idea, exc)
        body = _DRY_RUN_BODY_TEMPLATE.format(
            pain_snippet=_truncate(pain_snippet),
            idea=source_idea,
        ).strip()

    try:
        subject = router.complete("generation", subject_prompt, system_prompt=_OFFER_SYSTEM).strip()
    except Exception as exc:
        logger.warning("LLM subject generation failed for '%s': %s", source_idea, exc)
        subject = _DRY_RUN_SUBJECT_TEMPLATE.format(idea=source_idea)

    return subject, body


def _render_offer_md_primary(idea: dict, subject: str, body: str, generated_at: str) -> str:
    """Render a complete offer markdown with YAML front-matter (primary flow)."""
    frontmatter_data = {
        "idea": idea.get("source_idea", ""),
        "recipient": idea.get("source_author", ""),
        "source_url": idea.get("source_url", ""),
        "source_platform": idea.get("source_platform", idea.get("source", "")),
        "idea_score": idea.get("score", 0.0),
        "generated_at": generated_at,
        "status": "draft",
    }
    frontmatter = "---\n" + yaml.safe_dump(frontmatter_data, allow_unicode=True, sort_keys=False) + "---\n"
    return frontmatter + f"Subject: {subject}\n\n{body}\n"


def generate_from_connector(
    ideas: list[dict],
    output_dir: Path,
    dry_run: bool = False,
    min_score: float = _DEFAULT_MIN_SCORE,
) -> list[Path]:
    """Generate offer files from connector.json entries.

    Skips entries where source_author is empty or "unknown".
    Skips entries where score < min_score.
    Skips offer files that already exist (idempotent).

    Args:
        ideas:      list of dicts from connector.json
        output_dir: directory where offer_N.md files are written
        dry_run:    skip real LLM calls; use template-based placeholder
        min_score:  minimum idea score to include

    Returns:
        List of Path objects for each written file.
    """
    if not dry_run:
        from workspace.llm_router import router as _llm_router  # noqa: PLC0415
    else:
        _llm_router = None

    # Filter: skip unknown authors and low-score ideas
    eligible = [idea for idea in ideas if _is_eligible(idea, min_score)]

    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    offer_idx = 1
    for idea in eligible:
        out_path = output_dir / f"offer_{offer_idx}.md"

        # Idempotent: skip if file already exists
        if out_path.exists():
            logger.info("[OFFER] Skipping existing %s", out_path.name)
            offer_idx += 1
            continue

        author = idea.get("source_author", "")
        score = idea.get("score", 0.0)
        platform = idea.get("source_platform", idea.get("source", ""))

        subject, body = _generate_offer_from_idea(idea, _llm_router, dry_run=dry_run)
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        content = _render_offer_md_primary(idea, subject, body, generated_at)

        # Atomic write: write to .tmp then rename
        tmp_path = output_dir / f"offer_{offer_idx}.md.tmp"
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.rename(out_path)

        logger.info(
            "[OFFER] %s → @%s (score=%.2f, platform=%s)",
            out_path.name,
            author,
            score,
            platform,
        )
        written.append(out_path)
        offer_idx += 1

    return written


# ---------------------------------------------------------------------------
# Legacy flow — generate from matches.json
# ---------------------------------------------------------------------------


def _generate_offer_from_match(match: dict, router, dry_run: bool) -> str:
    """Generate a personalized outreach message for a single match.

    Returns the message body as a plain string.  On LLM error falls back
    to a template so the pipeline never produces an empty file.
    """
    company = match.get("lead_company", "Unknown")
    idea = match.get("idea", "our solution")
    lead_url = match.get("lead_url", "")
    match_reason = match.get("match_reason", "")

    pain = match_reason or "your infrastructure/automation challenges"

    if dry_run:
        return _LEGACY_DRY_RUN_TEMPLATE.format(
            company=company,
            lead_url=lead_url or "(no url)",
            pain_snippet=_truncate(pain),
            idea=idea,
        ).strip()

    prompt = _LEGACY_OFFER_PROMPT.format(
        company=company,
        pain=pain,
        idea=idea,
        lead_url=lead_url or "(no public url)",
    )

    try:
        text = router.complete("generation", prompt, system_prompt=_LEGACY_OFFER_SYSTEM)
        return text.strip()
    except Exception as exc:
        logger.warning(
            "LLM offer generation failed for '%s' × '%s': %s",
            idea,
            company,
            exc,
        )
        return _LEGACY_DRY_RUN_TEMPLATE.format(
            company=company,
            lead_url=lead_url or "(no url)",
            pain_snippet=_truncate(pain),
            idea=idea,
        ).strip()


def _render_offer_md_legacy(match: dict, body: str, created: str) -> str:
    """Render a complete offer markdown file with YAML front-matter (legacy)."""
    frontmatter_data = {
        "idea": match.get("idea", ""),
        "company": match.get("lead_company", "Unknown"),
        "fit_score": match.get("fit_score", 0.0),
        "lead_url": match.get("lead_url", ""),
        "lead_contact": match.get("lead_contact", ""),
        "created": created,
    }
    frontmatter = "---\n" + yaml.safe_dump(frontmatter_data, allow_unicode=True, sort_keys=False) + "---\n"
    return frontmatter + "\n" + body + "\n"


def generate(
    matches: list[dict],
    output_dir: Path,
    dry_run: bool = False,
) -> list[Path]:
    """Generate offer files for each match (sorted by fit_score descending).

    Legacy function retained for --from-matches mode and external callers.

    Args:
        matches:    list of match dicts from matches.json
        output_dir: directory where offer_N.md files are written
        dry_run:    skip real LLM calls; use template-based placeholder

    Returns:
        List of Path objects for each written file.
    """
    if not dry_run:
        from workspace.llm_router import router as _llm_router  # noqa: PLC0415
    else:
        _llm_router = None

    ranked = sorted(matches, key=lambda m: m.get("fit_score", 0.0), reverse=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for idx, match in enumerate(ranked, start=1):
        company = match.get("lead_company", "Unknown")
        idea = match.get("idea", "?")

        out_path = output_dir / f"offer_{idx}.md"

        # Idempotent: skip if file already exists
        if out_path.exists():
            logger.info("[OFFER] Skipping existing %s", out_path.name)
            written.append(out_path)
            continue

        logger.info(
            "[OFFER_GEN] Generating offer %d/%d: '%s' × '%s'",
            idx,
            len(ranked),
            idea,
            company,
        )

        body = _generate_offer_from_match(match, _llm_router, dry_run=dry_run)
        created_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        content = _render_offer_md_legacy(match, body, created_ts)

        tmp_path = output_dir / f"offer_{idx}.md.tmp"
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.rename(out_path)

        logger.info("[OFFER_GEN] Written → %s", out_path)
        written.append(out_path)

    return written


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offer Generator — personalized outreach from connector.json (Pipeline 3, Step 7). "
            "Use --from-matches for the legacy matches.json flow."
        )
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Specific run ID to read connector.json from (default: latest run)",
    )
    parser.add_argument(
        "--runs",
        default=str(_DEFAULT_RUNS_DIR),
        help=f"Path to workspace/runs/ directory (default: {_DEFAULT_RUNS_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT_DIR),
        help=f"Directory for offer_N.md files (default: {_DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM calls; use template-based placeholder messages",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=_DEFAULT_MIN_SCORE,
        help=f"Minimum idea score to include (default: {_DEFAULT_MIN_SCORE})",
    )
    # Legacy mode
    parser.add_argument(
        "--from-matches",
        action="store_true",
        help=(
            "Legacy mode: read matches.json instead of connector.json. "
            "Use --input to specify the matches file."
        ),
    )
    parser.add_argument(
        "--input",
        default=str(_DEFAULT_MATCHES_INPUT),
        help=f"[--from-matches only] Path to matches.json (default: {_DEFAULT_MATCHES_INPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)

    # ------------------------------------------------------------------
    # Legacy mode: read from matches.json
    # ------------------------------------------------------------------
    if args.from_matches:
        input_path = Path(args.input)
        if not input_path.exists():
            print(
                f"[OFFER] [FAIL] matches.json not found: {input_path}",
                file=sys.stderr,
            )
            sys.exit(1)

        matches = json.loads(input_path.read_text(encoding="utf-8"))
        if not matches:
            print("[OFFER] [FAIL] matches.json is empty — nothing to generate", file=sys.stderr)
            sys.exit(1)

        print(
            f"[OFFER] {len(matches)} matches loaded from {input_path} "
            f"(dry_run={args.dry_run})"
        )

        written = generate(matches, output_dir, dry_run=args.dry_run)
        print(f"[OFFER] Done — {len(written)} offers written")

        if not written:
            print("[OFFER] [WARN] 0 offers generated", file=sys.stderr)
            sys.exit(2)
        return

    # ------------------------------------------------------------------
    # Primary mode: read from connector.json
    # ------------------------------------------------------------------
    try:
        connector_path = find_connector_json(Path(args.runs), args.run_id)
    except FileNotFoundError as exc:
        print(f"[OFFER] [FAIL] {exc}", file=sys.stderr)
        sys.exit(1)

    run_id = connector_path.parent.name
    ideas = json.loads(connector_path.read_text(encoding="utf-8"))

    if not ideas:
        print("[OFFER] [FAIL] connector.json is empty — nothing to generate", file=sys.stderr)
        sys.exit(1)

    print(
        f"[OFFER] Run: {run_id} — {len(ideas)} idea(s) loaded "
        f"(dry_run={args.dry_run}, min_score={args.min_score})"
    )

    eligible_count = sum(1 for idea in ideas if _is_eligible(idea, args.min_score))

    written = generate_from_connector(
        ideas,
        output_dir,
        dry_run=args.dry_run,
        min_score=args.min_score,
    )
    print(f"[OFFER] Done — {len(written)} offers written")

    if eligible_count == 0:
        print(
            "[OFFER] [WARN] 0 offers generated — "
            "no ideas with a known author passed the score filter",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
