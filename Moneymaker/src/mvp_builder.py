"""Autonomous MVP Builder — Layer 4 of the MVP Idea Engine.

Converts a filtered idea into a concrete, actionable MVP plan including:
  - Chosen format (landing_page | telegram_bot | google_form_manual | api_wrapper)
  - Revenue model and price point
  - Estimated build time
  - Validation steps (how to reach first paying user)
  - Tech stack
  - A ready-to-use starter template / copy

Format selection heuristic
---------------------------
| Solution mentions…       | Format                |
|--------------------------|-----------------------|
| "bot", "telegram"        | telegram_bot          |
| "api", "integration",    | api_wrapper           |
|  "webhook"               |                       |
| manual / service /       | google_form_manual    |
|  concierge               |                       |
| everything else          | landing_page          |
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from textwrap import dedent

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import settings
from src.models import FilterResult, MVPFormat, MVPPlan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_BOT_RE = re.compile(r"\b(bot|telegram|discord|slack)\b", re.IGNORECASE)
_API_RE = re.compile(r"\b(api|integration|webhook|endpoint|connector|wrapper)\b", re.IGNORECASE)
_MANUAL_RE = re.compile(
    r"\b(manual|concierge|done.for.you|service|fulfil|fulfill|human.in.the.loop)\b",
    re.IGNORECASE,
)


def _choose_format(
    filter_result: FilterResult,
    format_weights: dict[str, float] | None = None,
) -> MVPFormat:
    text = f"{filter_result.idea.solution} {filter_result.idea.problem}"
    # Base scores: regex match adds 5.0 to make the signal dominant
    scores: dict[str, float] = {
        "telegram_bot": 1.0,
        "api_wrapper": 1.0,
        "google_form_manual": 1.0,
        "landing_page": 1.0,
    }
    if _BOT_RE.search(text):
        scores["telegram_bot"] += 5.0
    elif _API_RE.search(text):
        scores["api_wrapper"] += 5.0
    elif _MANUAL_RE.search(text):
        scores["google_form_manual"] += 5.0
    else:
        scores["landing_page"] += 5.0
    # Multiply by learned weights (minor influence on edge cases)
    if format_weights:
        for fmt, w in format_weights.items():
            if fmt in scores:
                scores[fmt] *= w
    return max(scores, key=scores.__getitem__)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_LANDING_PAGE_TEMPLATE = dedent(
    """
    <!-- Next.js / plain HTML landing page starter -->
    <html>
    <head><title>{title}</title></head>
    <body>
      <h1>{title}</h1>
      <p>{tagline}</p>
      <p>💸 {revenue_model} — starting at {price_point}</p>
      <form action="/api/waitlist" method="POST">
        <input name="email" type="email" placeholder="your@email.com" required />
        <button type="submit">Get Early Access →</button>
      </form>
    </body>
    </html>
    """
).strip()

_TELEGRAM_BOT_TEMPLATE = dedent(
    """
    # Telegram bot starter (python-telegram-bot v21)
    # pip install python-telegram-bot

    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    BOT_TOKEN = "YOUR_BOT_TOKEN"

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "👋 Welcome to {title}!\\n\\n{tagline}\\n\\n"
            "Send /help to see available commands."
        )

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Available commands:\\n/start — welcome\\n/run — run the main feature"
        )

    if __name__ == "__main__":
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_cmd))
        app.run_polling()
    """
).strip()

_GOOGLE_FORM_TEMPLATE = dedent(
    """
    # Google Form + Manual Fulfillment MVP

    ## Step 1 — Create Google Form
    Fields:
      1. Name (short answer)
      2. Email (short answer)
      3. Describe your current problem in detail (paragraph)
      4. How much would you pay per month for a solution? (multiple choice: $29 / $49 / $99 / Other)

    ## Step 2 — Connect to Google Sheets
    - Link the form to a Google Sheet for automatic response collection.

    ## Step 3 — Outreach template (cold DM / email)
    Subject: Quick question about {problem_short}

    Hi [Name],

    I'm building {title} — {tagline}

    I'd love to send you a free trial in exchange for 10 minutes of feedback.
    Interested? Fill this 1-min form: [FORM_LINK]

    ## Step 4 — Manual fulfillment checklist
    - [ ] Receive form submission
    - [ ] Deliver result within 24h via email
    - [ ] Follow up after 3 days
    - [ ] Ask for payment if they found value: {price_point}/mo
    """
).strip()

_API_WRAPPER_TEMPLATE = dedent(
    """
    # API Wrapper MVP starter (FastAPI)
    # pip install fastapi uvicorn httpx

    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import httpx

    app = FastAPI(title="{title}", description="{tagline}")

    class Request(BaseModel):
        input: str

    @app.post("/run")
    async def run(req: Request):
        \"\"\"Core endpoint — replace with actual upstream API call.\"\"\"
        async with httpx.AsyncClient() as client:
            # TODO: replace with real upstream API
            resp = await client.post("https://api.example.com/v1/run", json={{"input": req.input}})
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()

    # Run: uvicorn main:app --reload
    """
).strip()

_TEMPLATES: dict[MVPFormat, str] = {
    "landing_page": _LANDING_PAGE_TEMPLATE,
    "telegram_bot": _TELEGRAM_BOT_TEMPLATE,
    "google_form_manual": _GOOGLE_FORM_TEMPLATE,
    "api_wrapper": _API_WRAPPER_TEMPLATE,
}

_BUILD_TIMES: dict[MVPFormat, str] = {
    "landing_page": "2–4 hours",
    "telegram_bot": "3–6 hours",
    "google_form_manual": "1–2 hours",
    "api_wrapper": "4–8 hours",
}

# ---------------------------------------------------------------------------
# AI-powered plan generation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = dedent(
    """
    You are an expert solo-founder advisor who helps build MVPs in under 24 hours.
    Given a validated product idea and its chosen MVP format, produce an actionable plan.

    Return ONLY a JSON object with these keys:
      title            (string) – short product name
      tagline          (string) – one-line value proposition
      revenue_model    (string) – e.g. "Monthly SaaS subscription"
      price_point      (string) – e.g. "$49/mo"
      validation_steps (array of strings) – 3–5 concrete steps to reach first paying user
      tech_stack       (array of strings) – specific technologies/tools to use

    Output raw JSON only, no markdown or extra text.
    """
).strip()

_USER_TEMPLATE = dedent(
    """
    Idea:
    - Problem: {problem}
    - Target user: {target_user}
    - Solution: {solution}
    - Why now: {why_now}
    - Existing spend behavior: {spend}
    - MVP format chosen: {fmt}
    """
).strip()


@retry(
    retry=retry_if_exception_type(anthropic.APIError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
)
async def _ai_plan(client: anthropic.AsyncAnthropic, filter_result: FilterResult, fmt: MVPFormat) -> dict:
    idea = filter_result.idea
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _USER_TEMPLATE.format(
                    problem=idea.problem,
                    target_user=idea.target_user,
                    solution=idea.solution,
                    why_now=idea.why_now,
                    spend=idea.existing_spend_behavior,
                    fmt=fmt,
                ),
            },
        ],
    )
    content = response.content[0].text if response.content else "{}"
    return json.loads(content)


def _heuristic_plan(filter_result: FilterResult, fmt: MVPFormat) -> dict:
    """Fallback plan when Claude is unavailable."""
    idea = filter_result.idea
    words = idea.solution.split()
    title = " ".join(w.capitalize() for w in words[:3]) + "AI"
    return {
        "title": title,
        "tagline": idea.solution[:120],
        "revenue_model": "Monthly SaaS subscription",
        "price_point": "$49/mo",
        "validation_steps": [
            f"Post in 3 niche communities where {idea.target_user} hangs out",
            "DM 20 potential users with a personalised problem framing",
            "Offer a free 7-day trial in exchange for a 15-min onboarding call",
            "Charge on day 8 using Stripe Payment Link",
        ],
        "tech_stack": _default_stack(fmt),
    }


def _fill_template(tmpl: str, subs: dict[str, str]) -> str:
    """Single-pass template substitution — immune to brace injection in values."""
    pattern = re.compile(r"\{(" + "|".join(re.escape(k) for k in subs) + r")\}")
    return pattern.sub(lambda m: subs[m.group(1)], tmpl)


def _default_stack(fmt: MVPFormat) -> list[str]:
    stacks: dict[MVPFormat, list[str]] = {
        "landing_page": ["Next.js", "Tailwind CSS", "Vercel", "Stripe", "Resend"],
        "telegram_bot": ["Python", "python-telegram-bot", "Railway", "PostgreSQL"],
        "google_form_manual": ["Google Forms", "Google Sheets", "Zapier", "Gmail"],
        "api_wrapper": ["FastAPI", "httpx", "Render", "Stripe", "Redis"],
    }
    return stacks.get(fmt, ["Python", "FastAPI", "Stripe"])


# ---------------------------------------------------------------------------
# Public MVPBuilder class
# ---------------------------------------------------------------------------


class MVPBuilder:
    """Builds concrete MVP plans from filtered ideas."""

    def __init__(self, dry_run: bool = False, format_weights: dict[str, float] | None = None) -> None:
        self.dry_run = dry_run
        self._format_weights = format_weights or {}
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def build(self, filter_result: FilterResult) -> MVPPlan:
        """Build an MVP plan for a single passed filter result."""
        fmt = _choose_format(filter_result, self._format_weights or None)

        if self.dry_run or not settings.anthropic_api_key:
            raw = _heuristic_plan(filter_result, fmt)
        else:
            try:
                raw = await _ai_plan(self._get_client(), filter_result, fmt)
            except Exception as exc:
                logger.error("MVPBuilder Claude error, falling back to heuristic: %s", exc)
                raw = _heuristic_plan(filter_result, fmt)

        title = raw.get("title", "MVP")
        tagline = raw.get("tagline", filter_result.idea.solution)
        price_point = raw.get("price_point", "$49/mo")
        problem_short = filter_result.idea.problem[:50]

        template = _fill_template(
            _TEMPLATES.get(fmt, ""),
            {
                "title": title,
                "tagline": tagline,
                "revenue_model": raw.get("revenue_model", "Subscription"),
                "price_point": price_point,
                "problem_short": problem_short,
            },
        )

        plan = MVPPlan(
            filter_result=filter_result,
            format=fmt,
            title=title,
            tagline=tagline,
            revenue_model=raw.get("revenue_model", "Monthly SaaS subscription"),
            price_point=price_point,
            estimated_build_time=_BUILD_TIMES[fmt],
            validation_steps=raw.get("validation_steps", []),
            tech_stack=raw.get("tech_stack", _default_stack(fmt)),
            template=template,
        )

        logger.info(
            "MVPBuilder: plan '%s' (%s, %s).", plan.title, fmt, plan.estimated_build_time
        )
        return plan

    async def build_all(self, filter_results: list[FilterResult]) -> list[MVPPlan]:
        """Build MVP plans for all passed filter results."""
        return list(await asyncio.gather(*(self.build(fr) for fr in filter_results)))
