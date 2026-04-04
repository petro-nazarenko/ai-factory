"""
akf.py — AI Knowledge Filler (AKF)
STEP 3 of the AI Factory pipeline.

Takes a prompt from connector.json and generates a structured knowledge spec,
validated against the AKF schema before writing to disk.  LLM calls and
provider fallback are handled entirely by workspace/llm_router.py.

Usage:
    python akf.py generate "<prompt text>" --output /path/to/validated/ --slug idea_N
    python akf.py batch --input connector.json --output /path/to/validated/

Schema enforced:
    title:   string
    type:    guide | reference | checklist
    domain:  automation | maritime | api-design | devops
    level:   beginner | intermediate | advanced
    status:  active
    tags:    list[str] (min 3)
    created: ISO 8601
    updated: ISO 8601

Error codes (E001–E008):
    E001 – missing title
    E002 – invalid type value
    E003 – invalid domain value
    E004 – invalid level value
    E005 – missing or invalid status
    E006 – insufficient tags (< 3)
    E007 – invalid date format (created/updated)
    E008 – missing required field
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

# ---------------------------------------------------------------------------
# Router import — workspace/ is one level above ai-knowledge-filler/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../workspace"))
from llm_router import LLMRouterError, router  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

VALID_TYPES = {"guide", "reference", "checklist"}
VALID_DOMAINS = {"automation", "maritime", "api-design", "devops"}
VALID_LEVELS = {"beginner", "intermediate", "advanced"}
VALID_STATUSES = {"active"}
MIN_TAGS = 3
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = dedent("""
    You are a technical knowledge architect. Given a product idea prompt, you generate
    a structured solution specification formatted as a Markdown document with YAML
    frontmatter.

    CRITICAL FORMAT RULE: Your response MUST start with exactly three dashes "---" on
    the very first line. The frontmatter block MUST be closed with another line containing
    exactly "---" before any Markdown content begins. No text, blank lines, or code fences
    before the opening "---". Violation of this rule causes a hard parse failure.

    The frontmatter MUST contain exactly these fields:
      title:   <string — concise product/solution title>
      type:    <guide | reference | checklist>
      domain:  <automation | maritime | api-design | devops>
      level:   <beginner | intermediate | advanced>
      status:  active
      tags:    [tag1, tag2, tag3]   # minimum 3 tags
      created: <ISO 8601 datetime, e.g. 2026-04-03T14:25:00Z>
      updated: <ISO 8601 datetime, same as created>

    Choose domain based on the idea:
    - automation: workflow, SaaS, bots, scrapers, integrations
    - devops:     infrastructure, deployment, monitoring
    - api-design: API wrappers, integrations
    - maritime:   shipping, logistics, fleet

    The body MUST contain:
    ## Problem
    ## Target User
    ## Solution
    ## Revenue Model
    ## MVP Format
    ## Estimated Build Time
    ## Validation Steps
    ## Tech Stack

    EXAMPLE OF CORRECT OUTPUT FORMAT (follow this structure exactly):

    ---
    title: "Example Product Name"
    type: guide
    domain: automation
    level: beginner
    status: active
    tags: [automation, saas, freelance]
    created: "2026-04-03T14:25:00Z"
    updated: "2026-04-03T14:25:00Z"
    ---

    ## Problem
    Description of the problem.

    ## Target User
    Who experiences this problem.

    ## Solution
    What the product does.

    ## Revenue Model
    How it makes money.

    ## MVP Format
    The simplest shippable version.

    ## Estimated Build Time
    4 hours

    ## Validation Steps
    1. Step one.

    ## Tech Stack
    - Tool one

    Output the complete Markdown document (frontmatter + body). No extra commentary.
    Do not wrap your response in a code fence. Start your response with "---".
""").strip()

_CORRECTION_TEMPLATES = {
    "E001": "The title field is missing. Add a concise title to the frontmatter.",
    "E002": "The type field must be one of: guide, reference, checklist. Fix it.",
    "E003": "The domain field must be one of: automation, maritime, api-design, devops. Fix it.",
    "E004": "The level field must be one of: beginner, intermediate, advanced. Fix it.",
    "E005": "The status field must be 'active'. Fix it.",
    "E006": "The tags list must contain at least 3 items. Add more relevant tags.",
    "E007": "The created/updated fields must be valid ISO 8601 datetimes (e.g. 2026-04-03T14:25:00Z). Fix them.",
    "E008": "Your response did not start with '---'. The response MUST begin with exactly '---' on the first line, followed by YAML fields, then a closing '---', then the Markdown body. Do not include any text or code fences before the opening '---'.",
}

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter dict and body from a Markdown string."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        raise ValidationError("E008", "No YAML frontmatter found (expected --- block at top)")

    fm_text, body = match.group(1), match.group(2)
    fm: dict = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                fm[key] = [t.strip().strip('"').strip("'") for t in inner.split(",") if t.strip()]
            else:
                fm[key] = val
    return fm, body


def validate_schema(text: str) -> dict:
    """Validate AKF schema. Returns frontmatter dict on success. Raises ValidationError."""
    fm, _ = _parse_frontmatter(text)

    if not fm.get("title"):
        raise ValidationError("E001", "Missing 'title' field")
    if fm.get("type") not in VALID_TYPES:
        raise ValidationError("E002", f"Invalid type '{fm.get('type')}', must be one of {VALID_TYPES}")
    if fm.get("domain") not in VALID_DOMAINS:
        raise ValidationError("E003", f"Invalid domain '{fm.get('domain')}', must be one of {VALID_DOMAINS}")
    if fm.get("level") not in VALID_LEVELS:
        raise ValidationError("E004", f"Invalid level '{fm.get('level')}', must be one of {VALID_LEVELS}")
    if fm.get("status") not in VALID_STATUSES:
        raise ValidationError("E005", f"Invalid status '{fm.get('status')}', must be 'active'")

    tags = fm.get("tags", [])
    if not isinstance(tags, list) or len(tags) < MIN_TAGS:
        raise ValidationError("E006", f"Need at least {MIN_TAGS} tags, got {len(tags) if isinstance(tags, list) else 0}")

    for date_field in ("created", "updated"):
        val = fm.get(date_field, "")
        try:
            datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise ValidationError("E007", f"Invalid ISO 8601 date in '{date_field}': '{val}'")

    return fm


# ---------------------------------------------------------------------------
# Lead-source metadata injection
# ---------------------------------------------------------------------------


def _inject_lead_meta(text: str, meta: dict) -> str:
    """Append lead-source fields to validated frontmatter.

    Called after schema validation so the extra fields never interfere with
    the validator (which only checks the required AKF fields).
    """
    match = re.match(r"^(---\s*\n)(.*?)(\n---\s*\n)(.*)", text, re.DOTALL)
    if not match:
        return text
    opening, fm_text, closing, body = match.groups()

    lead_fields = []
    for key in ("source_url", "source_company", "source_author", "source_platform", "posted_date"):
        val = str(meta.get(key) or "").strip()
        if val:
            # Escape any quotes so the YAML stays valid
            lead_fields.append(f'{key}: "{val.replace(chr(34), chr(39))}"')

    if not lead_fields:
        return text

    injected_fm = fm_text + "\n" + "\n".join(lead_fields)
    return opening + injected_fm + closing + body


# ---------------------------------------------------------------------------
# Generate + validate with retry
# ---------------------------------------------------------------------------


def generate_and_validate(
    prompt: str,
    slug: str,
    output_dir: Path,
    now_iso: str,
    meta: dict | None = None,
) -> tuple[bool, str | None]:
    """Generate a spec via router, validate it, retry on schema errors.

    On each ValidationError the correction instruction is appended to the
    prompt and the router is called again (max MAX_RETRIES additional attempts).

    Returns:
        (success: bool, error_code_or_None: str | None)
    """
    last_error: ValidationError | None = None
    current_prompt = prompt

    for attempt in range(MAX_RETRIES + 1):
        print(f"  [AKF] {slug} attempt {attempt + 1}/{MAX_RETRIES + 1} [router]...", flush=True)
        try:
            text = router.complete("validation", current_prompt, system_prompt=_SYSTEM_PROMPT)

            # Inject today's date if model left placeholders
            text = re.sub(
                r'(created|updated):\s*["\']?<[^>]+>["\']?',
                lambda m: f"{m.group(1)}: {now_iso}",
                text,
            )

            validate_schema(text)

            if meta:
                text = _inject_lead_meta(text, meta)

            out_path = output_dir / f"{slug}.md"
            out_path.write_text(text, encoding="utf-8")
            print(f"  [AKF] {slug} → SUCCESS written to {out_path}")
            return True, None

        except ValidationError as exc:
            last_error = exc
            correction = _CORRECTION_TEMPLATES.get(exc.code, exc.message)
            print(f"  [AKF] {slug} schema error {exc.code}: {exc.message} — retrying with correction")
            # Append correction context so the next attempt self-corrects
            current_prompt = (
                f"{prompt}\n\n"
                f"Correction required: {correction}\n\n"
                f"Please regenerate the complete document."
            )

        except LLMRouterError as exc:
            print(f"  [AKF] {slug} → FAIL router exhausted: {exc}", file=sys.stderr)
            return False, "ROUTER_EXHAUSTED"

    code = last_error.code if last_error else "E008"
    print(f"  [AKF] {slug} → ABORT after {MAX_RETRIES + 1} attempts, last error: {code}")
    return False, code


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_generate(args: argparse.Namespace) -> None:
    """Generate a single spec from a prompt string."""
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    slug = args.slug or "idea"
    print(f"[AKF] Router status: { {k: v['available'] for k, v in router.status().items()} }")

    ok, _ = generate_and_validate(args.prompt, slug, output_dir, now_iso)
    sys.exit(0 if ok else 1)


def cmd_batch(args: argparse.Namespace) -> None:
    """Process all prompts from connector.json."""
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not input_path.exists():
        print(f"[AKF] [FAIL] connector.json not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    items: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))

    if not items:
        print("[AKF] [FAIL] connector.json is empty", file=sys.stderr)
        sys.exit(1)

    print(f"[AKF] Router status: { {k: v['available'] for k, v in router.status().items()} }")

    total = len(items)
    succeeded = 0
    aborted = 0

    for i, item in enumerate(items, 1):
        slug = f"idea_{i}"
        prompt = item.get("prompt", "")
        score = item.get("score", 0.0)
        source = item.get("source", "")
        meta = {
            "source_url": item.get("source_url", ""),
            "source_company": item.get("source_company", ""),
            "source_author": item.get("source_author", ""),
            "source_platform": item.get("source_platform", source),
            "posted_date": item.get("posted_date", ""),
        }

        print(f"[AKF] Processing {slug} (score={score}, source={source})")
        ok, _ = generate_and_validate(prompt, slug, output_dir, now_iso, meta=meta)
        if ok:
            succeeded += 1
        else:
            aborted += 1

    print(
        f"\n[AKF] DONE — {total} processed: "
        f"{succeeded} validated, {aborted} aborted"
    )

    if succeeded == 0:
        print("[AKF] [FAIL] No ideas validated — pipeline cannot proceed", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AKF — AI Knowledge Filler")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate a single spec")
    gen.add_argument("prompt", help="Prompt text")
    gen.add_argument("--output", required=True, help="Output directory")
    gen.add_argument("--slug", default="idea", help="Output filename (no extension)")
    gen.set_defaults(func=cmd_generate)

    bat = sub.add_parser("batch", help="Process all prompts from connector.json")
    bat.add_argument("--input", required=True, help="Path to connector.json")
    bat.add_argument("--output", required=True, help="Output directory for .md files")
    bat.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
