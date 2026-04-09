"""offer_generator.py — AI Factory STEP 7 (Pipeline 3)

Reads matches.json (output of matcher.py) and generates a personalized
outreach offer for each match using the LLM router.

Output: workspace/offers/offer_N.md  (one file per match, N = 1-indexed rank)

Markdown format per offer:
---
idea: "<idea title>"
company: "<lead company>"
fit_score: <float>
lead_url: "<hn post url>"
lead_contact: "<email or hn profile>"
created: "<ISO 8601>"
---

<personalized outreach message>

Usage:
    python workspace/offer_generator.py \\
        [--input workspace/matches/matches.json] \\
        [--output-dir workspace/offers/] \\
        [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default paths (relative to this file's location — workspace/)
# ---------------------------------------------------------------------------

_DEFAULT_INPUT = Path(__file__).resolve().parent / "matches" / "matches.json"
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "offers"

# ---------------------------------------------------------------------------
# LLM prompt
# ---------------------------------------------------------------------------

_OFFER_SYSTEM = (
    "You are an expert B2B outreach copywriter. "
    "Write concise, personalised cold-outreach messages that reference the "
    "prospect's specific pain, present the solution clearly, and end with a "
    "soft call-to-action (discovery call OR 1-week pilot). "
    "Return ONLY the message body — no subject line, no sign-off, no markdown fences."
)

_OFFER_PROMPT_TEMPLATE = """\
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

# ---------------------------------------------------------------------------
# Dry-run fallback message
# ---------------------------------------------------------------------------

_DRY_RUN_TEMPLATE = """\
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
# Core generation logic
# ---------------------------------------------------------------------------


def _generate_offer(match: dict, router, dry_run: bool) -> str:
    """Generate a personalized outreach message for a single match.

    Returns the message body as a plain string.  On LLM error the function
    logs a warning and returns a minimal templated fallback so the pipeline
    never produces an empty file.
    """
    company = match.get("lead_company", "Unknown")
    idea = match.get("idea", "our solution")
    lead_url = match.get("lead_url", "")
    match_reason = match.get("match_reason", "")

    # Use match_reason as pain proxy (it's a concise one-liner from the matcher)
    pain = match_reason or "your infrastructure/automation challenges"

    if dry_run:
        pain_snippet = pain[:80] + "…" if len(pain) > 80 else pain
        return _DRY_RUN_TEMPLATE.format(
            company=company,
            lead_url=lead_url or "(no url)",
            pain_snippet=pain_snippet,
            idea=idea,
        ).strip()

    prompt = _OFFER_PROMPT_TEMPLATE.format(
        company=company,
        pain=pain,
        idea=idea,
        lead_url=lead_url or "(no public url)",
    )

    try:
        text = router.complete("generation", prompt, system_prompt=_OFFER_SYSTEM)
        return text.strip()
    except Exception as exc:
        logger.warning(
            "LLM offer generation failed for '%s' × '%s': %s",
            idea,
            company,
            exc,
        )
        # Graceful degradation — return a templated placeholder
        pain_snippet = pain[:80] + "…" if len(pain) > 80 else pain
        return _DRY_RUN_TEMPLATE.format(
            company=company,
            lead_url=lead_url or "(no url)",
            pain_snippet=pain_snippet,
            idea=idea,
        ).strip()


def _render_offer_md(match: dict, body: str, created: str) -> str:
    """Render a complete offer markdown file with YAML front-matter."""
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate(
    matches: list[dict],
    output_dir: Path,
    dry_run: bool = False,
) -> list[Path]:
    """Generate offer files for each match (sorted by fit_score descending).

    Args:
        matches:    list of match dicts from matches.json
        output_dir: directory where offer_N.md files are written
        dry_run:    skip real LLM calls; use template-based placeholder

    Returns:
        List of Path objects for each written file.
    """
    if not dry_run:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from llm_router import router as _llm_router  # noqa: PLC0415
    else:
        _llm_router = None

    # Sort by fit_score descending (matches.json may already be sorted, but
    # we sort defensively in case the file was modified manually)
    ranked = sorted(matches, key=lambda m: m.get("fit_score", 0.0), reverse=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for idx, match in enumerate(ranked, start=1):
        company = match.get("lead_company", "Unknown")
        idea = match.get("idea", "?")

        logger.info(
            "[OFFER_GEN] Generating offer %d/%d: '%s' × '%s'",
            idx,
            len(ranked),
            idea,
            company,
        )

        body = _generate_offer(match, _llm_router, dry_run=dry_run)
        created_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        content = _render_offer_md(match, body, created_ts)

        out_path = output_dir / f"offer_{idx}.md"
        # Atomic write: write to .tmp then rename
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
        description="Offer Generator — personalized outreach per match (Pipeline 3, Step 7)"
    )
    parser.add_argument(
        "--input",
        default=str(_DEFAULT_INPUT),
        help=f"Path to matches.json (default: {_DEFAULT_INPUT})",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(
            f"[OFFER_GEN] [FAIL] matches.json not found: {input_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    matches = json.loads(input_path.read_text(encoding="utf-8"))
    if not matches:
        print("[OFFER_GEN] [FAIL] matches.json is empty — nothing to generate", file=sys.stderr)
        sys.exit(1)

    print(
        f"[OFFER_GEN] {len(matches)} matches loaded from {input_path} "
        f"(dry_run={args.dry_run})"
    )

    output_dir = Path(args.output_dir)
    written = generate(matches, output_dir, dry_run=args.dry_run)

    print(f"[OFFER_GEN] {len(written)} offer(s) written to {output_dir}")

    if not written:
        print("[OFFER_GEN] [WARN] 0 offers generated", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
