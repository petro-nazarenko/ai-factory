"""
connector.py — AI Factory STEP 2

Reads ideas.json (Moneymaker output), filters by score >= 7.0 (0–10 scale),
and maps each idea into AKF prompt format for STEP 3 validation.

Usage:
    python workspace/connector.py \
        --input workspace/runs/$RUN_ID/ideas.json \
        --output workspace/runs/$RUN_ID/connector.json
"""

import argparse
import json
import sys
from pathlib import Path

SCORE_THRESHOLD = 7.0  # Ideas must have score >= 7.0 (0–10 scale) to pass


def build_prompt(plan: dict) -> str:
    """Build AKF prompt from an MVPPlan dict (Moneymaker output)."""
    idea = plan.get("idea", {})
    parts = [f"Create a solution spec: {plan.get('title', idea.get('problem', ''))}"]
    if idea.get("target_user"):
        parts.append(f"Target user: {idea['target_user']}")
    if idea.get("solution"):
        parts.append(f"Solution: {idea['solution']}")
    if plan.get("revenue_model"):
        parts.append(f"Revenue model: {plan['revenue_model']}")
    return ". ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Connector: ideas.json → AKF input")
    parser.add_argument("--input", required=True, help="Path to ideas.json")
    parser.add_argument("--output", required=True, help="Path to write connector.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"[CONNECTOR] [FAIL] ideas.json not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    ideas = json.loads(input_path.read_text(encoding="utf-8"))

    if not ideas:
        print("[CONNECTOR] [FAIL] ideas.json is empty — aborting", file=sys.stderr)
        sys.exit(1)

    passed = []
    for plan in ideas:
        score = plan.get("filter_result", {}).get("score", 0.0)
        if score >= SCORE_THRESHOLD:
            signal = plan.get("filter_result", {}).get("idea", {}).get("signal", {})
            passed.append({
                "prompt": build_prompt(plan),
                "score": score,
                "source_idea": plan.get("title", ""),
                "source": signal.get("source", ""),
                "source_url": signal.get("source_url", ""),
                "source_author": signal.get("source_author", ""),
                "source_company": signal.get("source_company", ""),
                "source_text": signal.get("source_text", ""),
                "source_platform": signal.get("source", ""),
                "posted_date": signal.get("posted_date", ""),
            })

    total = len(ideas)
    n_passed = len(passed)
    print(f"[CONNECTOR] {total} ideas → {n_passed} passed filter (score >= {SCORE_THRESHOLD})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(passed, indent=2, ensure_ascii=False), encoding="utf-8")

    if n_passed == 0:
        print("[CONNECTOR] [WARN] 0 ideas passed — nothing to send to AKF", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
