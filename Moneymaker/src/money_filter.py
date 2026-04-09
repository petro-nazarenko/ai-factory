"""Money Filter Engine — Layer 3 of the MVP Idea Engine.

100% rule-based. Zero LLM calls. Zero network calls.

An idea passes the filter *only if* it satisfies all four criteria:

1. **Existing spending behavior** – the target user already pays for adjacent tools.
2. **Clear buyer** – there is a specific, identifiable person who would buy on day 1.
3. **MVP feasible in ≤ 24 h** – the first version can be built solo in a day.
4. **Sellable without brand** – you can close the first sale with no audience/brand.

Evaluation order:
  1. Hard rejects  — FUTURE_MARKET / NO_BUDGET / SOCIAL_ONLY patterns → instant reject
  2. Positive flags — has_budget / clear_buyer / mvp_feasible derived from
                      signal metadata + idea text
  3. Flag + score decision table:
       n_flags == 3                    → PASS
       n_flags == 2, signal.score >= 7 → PASS  (strong raw signal compensates)
       n_flags == 2, signal.score < 7  → REJECT (reason = missing flag)
       n_flags == 1                    → REJECT (reason = weakest dimension)
       n_flags == 0                    → REJECT
"""

from __future__ import annotations

import asyncio
import logging
import re

from src.models import FilterResult, Idea, RejectReason

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------

# Miner score at or above this value counts as a confirmed budget signal
_SIGNAL_SCORE_BUDGET_THRESHOLD = 7.0

# Miner score at or above this value lets a 2-flag idea pass
_SIGNAL_SCORE_PASS_THRESHOLD = 7.0

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_FUTURE_MARKET = re.compile(
    r"\b(will need|eventually|future|when .{0,20}matures|emerging market|"
    r"once .{0,20}grows|potential market)\b",
    re.IGNORECASE,
)
_NO_BUDGET = re.compile(
    r"\b(student|hobbyist|non.?profit|volunteer|free tier only|no budget|"
    r"can\'t afford|too expensive for them)\b",
    re.IGNORECASE,
)
_SOCIAL_ONLY = re.compile(
    r"\b(network effect|needs .{0,20}users to be useful|viral|social platform|"
    r"community.driven only|only valuable at scale)\b",
    re.IGNORECASE,
)
_SPEND_SIGNALS = re.compile(
    r"\b(already pay|currently pay|subscribe|paying for|tool budget|per month|/mo|SaaS|"
    r"subscription|annual plan|license fee|enterprise|pay for|paid plan|paid tool|"
    r"spend on|budget for|invest in|tool stack|developer tool|cloud service|"
    r"GitHub|Jira|Linear|Notion|Slack|AWS|Vercel|Heroku|Stripe|Zapier|"
    r"per seat|per user|annually|license)\b",
    re.IGNORECASE,
)
_BUYER_SIGNALS = re.compile(
    r"\b(freelance|freelancer|consultant|agency|founder|developer|marketer|e.?commerce|"
    r"store owner|recruiter|sales rep|accountant|engineer|manager|operator)\b",
    re.IGNORECASE,
)
_SIMPLE_MVP = re.compile(
    r"\b(form|landing page|email|spreadsheet|zapier|notion|bot|webhook|API wrapper|"
    r"chrome extension|simple script|one.?click|dashboard|automation|integration)\b",
    re.IGNORECASE,
)
_NO_BRAND = re.compile(
    r"\b(cold outreach|direct message|cold email|ProductHunt|AppSumo|niche forum|"
    r"community|reddit post|listing|directory)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Core evaluation — fully deterministic
# ---------------------------------------------------------------------------

def _evaluate(idea: Idea) -> dict:
    """Return a result dict for any idea without any LLM or network call."""
    combined = " ".join([
        idea.problem, idea.target_user, idea.solution,
        idea.why_now, idea.existing_spend_behavior,
        idea.signal.who_is_complaining, idea.signal.what_they_want,
        idea.signal.current_workaround, idea.signal.raw_text,
    ])

    # --- Hard rejects ---
    if _FUTURE_MARKET.search(combined):
        return {
            "passed": False, "score": 2.0,
            "reject_reason": RejectReason.FUTURE_MARKET.value,
            "reasoning": "Rule: future/emerging market framing detected.",
            "has_existing_spending": 2.0, "has_clear_buyer": 3.0,
            "mvp_feasible_24h": 5.0, "sells_without_brand": 3.0,
        }
    if _NO_BUDGET.search(combined):
        return {
            "passed": False, "score": 2.5,
            "reject_reason": RejectReason.NO_BUDGET_USERS.value,
            "reasoning": "Rule: no-budget user segment detected.",
            "has_existing_spending": 1.0, "has_clear_buyer": 4.0,
            "mvp_feasible_24h": 6.0, "sells_without_brand": 3.0,
        }
    if _SOCIAL_ONLY.search(combined):
        return {
            "passed": False, "score": 3.0,
            "reject_reason": RejectReason.SOCIAL_ONLY_VALUE.value,
            "reasoning": "Rule: network-effect dependency detected.",
            "has_existing_spending": 3.0, "has_clear_buyer": 3.0,
            "mvp_feasible_24h": 5.0, "sells_without_brand": 2.0,
        }

    # --- Positive flags ---
    has_budget = (
        idea.signal.score >= _SIGNAL_SCORE_BUDGET_THRESHOLD
        or _SPEND_SIGNALS.search(idea.existing_spend_behavior) is not None
        or _SPEND_SIGNALS.search(idea.signal.raw_text) is not None
    )
    clear_buyer = _BUYER_SIGNALS.search(idea.target_user) is not None
    mvp_feasible = _SIMPLE_MVP.search(idea.solution) is not None

    n_flags = sum([has_budget, clear_buyer, mvp_feasible])

    brand_score = 7.5 if _NO_BRAND.search(combined) else 6.5

    # --- Decision table ---
    if n_flags == 3:
        spend = 8.5 if has_budget else 6.0
        buyer = 8.5 if clear_buyer else 6.0
        mvp   = 8.0 if mvp_feasible else 6.0
        total = round((spend + buyer + mvp + brand_score) / 4, 2)
        return {
            "passed": True, "score": total, "reject_reason": None,
            "reasoning": "All three positive signals confirmed.",
            "has_existing_spending": spend, "has_clear_buyer": buyer,
            "mvp_feasible_24h": mvp, "sells_without_brand": brand_score,
        }

    if n_flags == 2 and idea.signal.score >= _SIGNAL_SCORE_PASS_THRESHOLD:
        spend = 8.0 if has_budget else 6.0
        buyer = 8.0 if clear_buyer else 6.0
        mvp   = 7.5 if mvp_feasible else 6.0
        total = round((spend + buyer + mvp + brand_score) / 4, 2)
        return {
            "passed": True, "score": total, "reject_reason": None,
            "reasoning": (
                f"Two positive signals confirmed; strong raw signal score "
                f"({idea.signal.score:.1f}) compensates."
            ),
            "has_existing_spending": spend, "has_clear_buyer": buyer,
            "mvp_feasible_24h": mvp, "sells_without_brand": brand_score,
        }

    if n_flags == 2:
        # Weak signal score — reject on the missing flag
        if not has_budget:
            reason = RejectReason.NO_BUDGET_USERS.value
            msg = "Weak signal score and no confirmed budget behaviour."
        elif not clear_buyer:
            reason = RejectReason.NO_CLEAR_BUYER.value
            msg = "Weak signal score and no identifiable day-1 buyer."
        else:
            reason = RejectReason.MVP_TOO_COMPLEX.value
            msg = "Weak signal score and no simple-MVP indicator in solution."
        spend = 7.5 if has_budget else 5.0
        buyer = 7.5 if clear_buyer else 5.0
        mvp   = 7.0 if mvp_feasible else 5.0
        total = round((spend + buyer + mvp + brand_score) / 4, 2)
        return {
            "passed": False, "score": total, "reject_reason": reason,
            "reasoning": f"Rule: {msg}",
            "has_existing_spending": spend, "has_clear_buyer": buyer,
            "mvp_feasible_24h": mvp, "sells_without_brand": brand_score,
        }

    if n_flags == 1:
        if not has_budget:
            reason = RejectReason.NO_BUDGET_USERS.value
            msg = "No confirmed budget behaviour."
        elif not clear_buyer:
            reason = RejectReason.NO_CLEAR_BUYER.value
            msg = "No identifiable day-1 buyer."
        else:
            reason = RejectReason.MVP_TOO_COMPLEX.value
            msg = "No simple-MVP indicator in solution."
        spend = 6.5 if has_budget else 4.0
        buyer = 6.5 if clear_buyer else 4.0
        mvp   = 6.0 if mvp_feasible else 4.0
        total = round((spend + buyer + mvp + brand_score) / 4, 2)
        return {
            "passed": False, "score": total, "reject_reason": reason,
            "reasoning": f"Rule: only one positive signal. {msg}",
            "has_existing_spending": spend, "has_clear_buyer": buyer,
            "mvp_feasible_24h": mvp, "sells_without_brand": brand_score,
        }

    # n_flags == 0
    return {
        "passed": False, "score": 4.0, "reject_reason": RejectReason.NO_BUDGET_USERS.value,
        "reasoning": "Rule: no budget, buyer, or feasibility signals detected.",
        "has_existing_spending": 4.0, "has_clear_buyer": 4.5,
        "mvp_feasible_24h": 5.0, "sells_without_brand": 5.5,
    }


# Alias for backwards compatibility and test imports
_heuristic_score = _evaluate


# ---------------------------------------------------------------------------
# Public MoneyFilter class
# ---------------------------------------------------------------------------


class MoneyFilter:
    """Filters ideas by monetization potential. Fully rule-based — no LLM calls."""

    def __init__(self, dry_run: bool = False) -> None:
        # dry_run kept for API compatibility; behaviour is identical either way
        self.dry_run = dry_run

    async def evaluate(self, idea: Idea) -> FilterResult:
        """Score a single idea deterministically."""
        raw = _evaluate(idea)

        reject_reason: RejectReason | None = None
        raw_reason = raw.get("reject_reason")
        if raw_reason:
            try:
                reject_reason = RejectReason(raw_reason)
            except ValueError:
                logger.warning(
                    "MoneyFilter: unknown reject_reason %r — leaving as None.",
                    raw_reason,
                )

        logger.debug(
            "MoneyFilter: '%s...' → %s (score=%.1f, flags=%s)",
            idea.problem[:50],
            "PASS" if raw["passed"] else "REJECT",
            raw["score"],
            raw.get("reasoning", ""),
        )

        return FilterResult(
            idea=idea,
            passed=bool(raw.get("passed", False)),
            score=float(raw.get("score", 0.0)),
            reject_reason=reject_reason,
            reasoning=str(raw.get("reasoning", "")),
            has_existing_spending=float(raw.get("has_existing_spending", 0.0)),
            has_clear_buyer=float(raw.get("has_clear_buyer", 0.0)),
            mvp_feasible_24h=float(raw.get("mvp_feasible_24h", 0.0)),
            sells_without_brand=float(raw.get("sells_without_brand", 0.0)),
        )

    async def filter_all(self, ideas: list[Idea]) -> list[FilterResult]:
        """Evaluate all ideas and return only the ones that passed."""
        results: list[FilterResult] = list(
            await asyncio.gather(*(self.evaluate(idea) for idea in ideas))
        )
        passed = [r for r in results if r.passed]
        for result in results:
            logger.info(
                "MoneyFilter: '%s...' → %s (score=%.1f)",
                result.idea.problem[:60],
                "PASS ✅" if result.passed else "FAIL ❌",
                result.score,
            )
        logger.info(
            "MoneyFilter: %d/%d ideas passed (rule-based, 0 LLM calls).",
            len(passed), len(results),
        )
        return passed
