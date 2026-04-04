"""Manual Fulfillment — Layer 5 of the MVP Idea Engine.

For each MVP plan the agent either:
  1. Simulates the backend service via an LLM call (``dry_run=False`` with API key), or
  2. Produces a deterministic mock output (``dry_run=True`` or no API key).

The result is a :class:`FulfillmentResult` that contains the delivered output
(e.g. a proposal draft, a price report, a testimonial script) so it can be
sent to the first lead or used as a demo asset in distribution posts.
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
from src.models import FulfillmentResult, FulfillmentStatus, MVPPlan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AI simulation prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = dedent(
    """
    You are an expert solo-founder executing a manual MVP service for a customer.
    Given a product plan, simulate the actual service delivery for a typical first customer.

    Produce a realistic, professional output that the founder would send/deliver to the customer.
    This could be a written report, analysis, formatted document, script, or any relevant artifact.

    Return ONLY a JSON object with these keys:
      output  (string) – the full delivered service artifact (2–5 paragraphs)
      notes   (string) – one sentence describing what was done and how

    Output raw JSON only, no markdown or extra text.
    """
).strip()

_USER_TEMPLATE = dedent(
    """
    Product plan:
    - Title: {title}
    - Tagline: {tagline}
    - Problem solved: {problem}
    - Target user: {target_user}
    - Solution: {solution}
    - Revenue model: {revenue_model} at {price_point}
    - MVP format: {fmt}

    Simulate fulfilling this service for a first customer and return the deliverable.
    """
).strip()

# ---------------------------------------------------------------------------
# Mock output used in dry-run / no-API mode
# ---------------------------------------------------------------------------

_MOCK_OUTPUTS: dict[str, str] = {
    "landing_page": dedent(
        """
        Hi [Customer Name],

        Thank you for signing up for early access! Here is your personalised preview report:

        **Your current problem:** You are spending 45+ minutes manually reformatting client briefs
        into polished proposals. Our tool eliminates this entirely.

        **What we've prepared for you:**
        - A proposal template pre-filled with your typical client details.
        - Three headline variants A/B tested for your niche.
        - A one-click PDF export ready for your next client meeting.

        You can access your dashboard at: https://app.example.com/dashboard

        We'd love your feedback — reply to this email or book a 10-min call.

        Best,
        The {title} Team
        """
    ).strip(),
    "telegram_bot": dedent(
        """
        [Bot simulation output]

        /start → Welcome to {title}! {tagline}

        /run → Processing your request…

        ✅ Done! Here is your result:

        Based on the inputs you provided, the automated analysis is complete.
        Your report has been generated and is ready to download.

        Use /export to download your result as a PDF.
        Use /help for more commands.
        """
    ).strip(),
    "google_form_manual": dedent(
        """
        Subject: Your {title} result is ready — delivered within 24 h ✅

        Hi [Customer Name],

        I manually processed your request from the form you submitted.

        Here is your custom deliverable:

        1. **Problem summary:** Based on your description, the core issue is [summarised problem].
        2. **Recommended solution:** [Tailored recommendation based on their inputs].
        3. **Next steps:** [3 concrete action items].

        This took me about 90 minutes to put together manually. If you found this valuable,
        I'd love to keep working with you on a recurring basis for {price_point}/mo.

        Reply to this email to get started. I only take 5 clients per month.

        Cheers,
        [Founder Name]
        """
    ).strip(),
    "api_wrapper": dedent(
        """
        API Simulation Response
        -----------------------
        Endpoint: POST /run
        Status: 200 OK

        {{
          "status": "success",
          "input": "[customer input]",
          "result": "Processed output from the upstream API wrapper.",
          "usage": {{
            "tokens_used": 512,
            "credits_remaining": 488
          }},
          "message": "Your request was processed successfully. {tagline}"
        }}
        """
    ).strip(),
}

_MOCK_NOTES = "Simulated fulfillment using a mock template (dry-run mode)."


@retry(
    retry=retry_if_exception_type(anthropic.APIError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
)
async def _ai_fulfill(client: anthropic.AsyncAnthropic, plan: MVPPlan) -> dict:
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _USER_TEMPLATE.format(
                    title=plan.title,
                    tagline=plan.tagline,
                    problem=plan.idea.problem,
                    target_user=plan.idea.target_user,
                    solution=plan.idea.solution,
                    revenue_model=plan.revenue_model,
                    price_point=plan.price_point,
                    fmt=plan.format,
                ),
            },
        ],
    )
    content = response.content[0].text if response.content else "{}"
    return json.loads(content)


def _fill(tmpl: str, subs: dict[str, str]) -> str:
    pattern = re.compile(r"\{(" + "|".join(re.escape(k) for k in subs) + r")\}")
    return pattern.sub(lambda m: subs[m.group(1)], tmpl)


def _mock_fulfill(plan: MVPPlan) -> dict:
    """Return a deterministic mock fulfillment for the given plan."""
    raw_output = _MOCK_OUTPUTS.get(plan.format, _MOCK_OUTPUTS["landing_page"])
    output = _fill(raw_output, {
        "title": plan.title,
        "tagline": plan.tagline,
        "price_point": plan.price_point,
    })
    return {"output": output, "notes": _MOCK_NOTES}


# ---------------------------------------------------------------------------
# Public ManualFulfillment class
# ---------------------------------------------------------------------------


class ManualFulfillment:
    """Executes (or simulates) the MVP service and produces a deliverable."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def fulfill(self, plan: MVPPlan) -> FulfillmentResult:
        """Fulfill (or simulate) a single MVP plan."""
        simulated = False

        if self.dry_run or not settings.anthropic_api_key:
            raw = _mock_fulfill(plan)
            simulated = True
            status = FulfillmentStatus.SIMULATED
        else:
            try:
                raw = await _ai_fulfill(self._get_client(), plan)
                status = FulfillmentStatus.COMPLETED
            except Exception as exc:
                logger.error("ManualFulfillment Claude error, falling back to mock: %s", exc)
                raw = _mock_fulfill(plan)
                simulated = True
                status = FulfillmentStatus.SIMULATED

        result = FulfillmentResult(
            plan=plan,
            status=status,
            output=str(raw.get("output", "")),
            notes=str(raw.get("notes", "")),
            simulated=simulated,
        )
        logger.info(
            "ManualFulfillment: '%s' → %s (simulated=%s).",
            plan.title,
            status.value,
            simulated,
        )
        return result

    async def fulfill_all(self, plans: list[MVPPlan]) -> list[FulfillmentResult]:
        """Fulfill all MVP plans concurrently and return results."""
        return list(await asyncio.gather(*(self.fulfill(plan) for plan in plans)))
