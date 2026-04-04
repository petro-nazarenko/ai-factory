"""Idea Generator — Layer 2 of the MVP Idea Engine.

Converts pain signals into concrete product ideas via llm_router.
Provider selection, TPM/TPD tracking and 429 fallback are handled
entirely by the router — this module only builds prompts and parses JSON.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from textwrap import dedent

# ---------------------------------------------------------------------------
# Router import — workspace/ is two levels above Moneymaker/src/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../workspace"))
from llm_router import LLMRouterError, router  # noqa: E402

from src.config import settings
from src.models import Idea, PainSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = dedent(
    """
    You are an expert startup idea generator with deep knowledge of B2B SaaS,
    micro-SaaS, and solo-founder businesses. You identify product ideas that
    can reach $1k MRR quickly because they solve genuine, recurring pains for
    people who already spend money on related solutions.

    For each pain signal you receive, generate exactly {n} distinct product ideas.
    Return ONLY a JSON array of objects with these keys:
      - problem          (string) – crisp one-line problem statement
      - target_user      (string) – specific persona, e.g. "freelance copywriter with 3-5 clients"
      - solution         (string) – what the product does (one sentence)
      - why_now          (string) – why this is the right moment to build it
      - existing_spend_behavior (string) – evidence the target user already pays for adjacent tools

    Do not include any explanation, markdown, or extra keys. Output raw JSON only.
    """
).strip()

_USER_TEMPLATE = dedent(
    """
    Pain signal:
    - Who is complaining: {who}
    - What they want: {what}
    - Current workaround: {workaround}
    - Source: {source}

    Generate {n} product ideas.
    """
).strip()

_BATCH_SYSTEM_PROMPT = dedent(
    """
    You are an expert startup idea generator with deep knowledge of B2B SaaS,
    micro-SaaS, and solo-founder businesses. You identify product ideas that
    can reach $1k MRR quickly because they solve genuine, recurring pains for
    people who already spend money on related solutions.

    You will receive multiple numbered pain signals. For each signal, generate
    exactly {n} distinct product ideas.

    Return ONLY a flat JSON array of idea objects. Each object MUST include a
    "signal_index" key (integer, 0-based) matching the signal it came from, plus:
      - signal_index     (int)    – index of the source signal (0-based)
      - problem          (string) – crisp one-line problem statement
      - target_user      (string) – specific persona, e.g. "freelance copywriter with 3-5 clients"
      - solution         (string) – what the product does (one sentence)
      - why_now          (string) – why this is the right moment to build it
      - existing_spend_behavior (string) – evidence the target user already pays for adjacent tools

    Do not include any explanation, markdown, or extra keys. Output raw JSON only.
    """
).strip()


def _build_batch_user_prompt(signals: list[PainSignal], n: int) -> str:
    lines = [f"Generate {n} ideas per signal ({len(signals)} signals total):\n"]
    for i, s in enumerate(signals):
        lines.append(
            f"Signal {i}:\n"
            f"- Who is complaining: {s.who_is_complaining}\n"
            f"- What they want: {s.what_they_want}\n"
            f"- Current workaround: {s.current_workaround}\n"
            f"- Source: {s.source.value}\n"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Mock ideas used in dry-run mode
# ---------------------------------------------------------------------------

_MOCK_IDEAS = [
    {
        "problem": "Freelancers spend 45+ minutes per client reformatting briefs into proposals",
        "target_user": "Freelance copywriter with 3–10 clients",
        "solution": "A web app that converts a raw brief (pasted text) into a polished proposal PDF in one click",
        "why_now": "LLMs make high-quality text transformation cheap; clients expect professional proposals",
        "existing_spend_behavior": "Most freelancers already pay for Notion, Google Workspace, or Bonsai ($20–$50/mo)",
    },
    {
        "problem": "E-commerce owners manually check competitor prices every morning",
        "target_user": "Shopify store owner earning $10k–$100k/mo",
        "solution": "A lightweight SaaS that monitors up to 20 competitor URLs and emails a daily price delta report",
        "why_now": "Pricing parity is critical during current inflationary period; no cheap self-serve tool exists",
        "existing_spend_behavior": "Merchants already pay for tools like Klaviyo, Privy, and ReConvert ($30–$100/mo each)",
    },
    {
        "problem": "Solo founders struggle to collect video testimonials without expensive software",
        "target_user": "B2B SaaS founder with 10–100 customers",
        "solution": "A one-page link customers open on mobile to record a 60-second testimonial video, no app install",
        "why_now": "Video social proof is proven to increase conversions; Testimonial.to charges $50+/mo",
        "existing_spend_behavior": "Founders already pay for Loom, UserEvidence, or Boast.io for similar outcomes",
    },
]

# ---------------------------------------------------------------------------
# JSON parsing helper
# ---------------------------------------------------------------------------


def _parse_ideas_json(raw: str) -> list[dict]:
    """Extract a JSON array from the model response (handles markdown fences)."""
    text = raw.strip()
    # Strip optional ```json ... ``` fences
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    data = json.loads(text)
    if isinstance(data, list):
        return data
    for value in data.values():
        if isinstance(value, list):
            return value
    return []


# ---------------------------------------------------------------------------
# IdeaGenerator
# ---------------------------------------------------------------------------


class IdeaGenerator:
    """Generates product ideas from pain signals via llm_router.

    All provider selection, rate-limit tracking, and failover are delegated
    to the shared router singleton.  This class only owns prompt construction
    and JSON → Idea mapping.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def _build_ideas(self, raw_ideas: list[dict], signal: PainSignal) -> list[Idea]:
        ideas: list[Idea] = []
        for raw in raw_ideas:
            try:
                ideas.append(Idea(
                    problem=raw["problem"],
                    target_user=raw["target_user"],
                    solution=raw["solution"],
                    why_now=raw["why_now"],
                    existing_spend_behavior=raw["existing_spend_behavior"],
                    signal=signal,
                ))
            except (KeyError, TypeError) as exc:
                logger.warning("IdeaGenerator: skipping malformed idea dict: %s — %s", raw, exc)
        return ideas

    async def generate(self, signal: PainSignal, n: int | None = None) -> list[Idea]:
        """Return up to *n* ideas for a single pain signal."""
        n = n or settings.ideas_per_signal

        if self.dry_run:
            return self._build_ideas(_MOCK_IDEAS[:n], signal)

        prompt = _USER_TEMPLATE.format(
            who=signal.who_is_complaining,
            what=signal.what_they_want,
            workaround=signal.current_workaround,
            source=signal.source.value,
            n=n,
        )
        system = _SYSTEM_PROMPT.format(n=n)

        try:
            raw_text = await router.acomplete("generation", prompt, system_prompt=system)
            raw_ideas = _parse_ideas_json(raw_text)
            ideas = self._build_ideas(raw_ideas, signal)
            logger.info("IdeaGenerator: %d ideas for signal from %s.", len(ideas), signal.source.value)
            return ideas
        except LLMRouterError as exc:
            logger.error("IdeaGenerator: all providers failed for signal from %s: %s",
                         signal.source.value, exc)
            return []
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("IdeaGenerator: parse error for signal from %s: %s",
                         signal.source.value, exc)
            return []

    async def generate_all(
        self,
        signals: list[PainSignal],
        n: int | None = None,
    ) -> list[Idea]:
        """Generate ideas for all signals in a single batch LLM call.

        Falls back to per-signal calls only if the batch call fails entirely.
        """
        if not signals:
            return []
        n = n or settings.ideas_per_signal

        if self.dry_run:
            results = await asyncio.gather(*(self.generate(s, n) for s in signals))
            return [idea for batch in results for idea in batch]

        batch_prompt = _build_batch_user_prompt(signals, n)
        system = _BATCH_SYSTEM_PROMPT.format(n=n)

        try:
            raw_text = await router.acomplete("generation", batch_prompt, system_prompt=system)
            raw_ideas = _parse_ideas_json(raw_text)

            if not raw_ideas:
                raise ValueError("empty batch result")

            logger.info("IdeaGenerator: batch returned %d raw ideas for %d signals.",
                        len(raw_ideas), len(signals))

            ideas: list[Idea] = []
            for raw in raw_ideas:
                idx = raw.get("signal_index")
                if idx is None or not isinstance(idx, int) or idx < 0 or idx >= len(signals):
                    logger.warning("IdeaGenerator: skipping idea with invalid signal_index %r", idx)
                    continue
                ideas.extend(self._build_ideas([raw], signals[idx]))

            logger.info("IdeaGenerator: %d ideas built from batch (%d signals, %d each).",
                        len(ideas), len(signals), n)
            return ideas

        except (LLMRouterError, ValueError, json.JSONDecodeError, Exception) as exc:
            logger.warning("IdeaGenerator: batch call failed (%s) — falling back to per-signal calls.", exc)
            results = await asyncio.gather(*(self.generate(s, n) for s in signals))
            return [idea for batch in results for idea in batch]
