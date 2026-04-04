"""Pydantic-based data models for the MVP Idea Engine v2 pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# Layer 1: Signal Miner output
# ---------------------------------------------------------------------------


class SignalSource(str, Enum):
    REDDIT = "reddit"
    PRODUCTHUNT = "producthunt"
    INDIEHACKERS = "indiehackers"
    JOBBOARDS = "jobboards"
    MOCK = "mock"


class PainSignal(BaseModel):
    """Represents a discovered pain signal from any source."""

    source: SignalSource
    source_url: str = ""
    source_author: str = Field(default="", description="Username or name of the person who posted.")
    source_company: str = Field(default="", description="Company or organisation associated with the signal.")
    source_text: str = Field(default="", description="Original untruncated post/job text.")
    posted_date: str = Field(default="", description="ISO 8601 date when the signal was originally posted.")
    who_is_complaining: str = Field(..., description="The persona / audience experiencing the pain.")
    what_they_want: str = Field(..., description="The outcome or capability they are seeking.")
    current_workaround: str = Field(
        ...,
        description="How they currently cope with the problem (if any).",
    )
    raw_text: str = Field(default="", description="Original content used to derive this signal.")
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Relevance / pain intensity score (0–10).",
    )


# ---------------------------------------------------------------------------
# Layer 2: Idea Generator output
# ---------------------------------------------------------------------------


class Idea(BaseModel):
    """A product idea generated from a pain signal."""

    problem: str
    target_user: str
    solution: str
    why_now: str
    existing_spend_behavior: str = Field(
        ...,
        description="Evidence that the target user already spends money on related solutions.",
    )
    signal: PainSignal


# ---------------------------------------------------------------------------
# Layer 3: Money Filter output
# ---------------------------------------------------------------------------


class RejectReason(str, Enum):
    FUTURE_MARKET = "future_market"
    NO_BUDGET_USERS = "no_budget_users"
    SOCIAL_ONLY_VALUE = "social_only_value"
    NO_CLEAR_BUYER = "no_clear_buyer"
    MVP_TOO_COMPLEX = "mvp_too_complex"


class FilterResult(BaseModel):
    """Outcome of the Money Filter Engine for a single idea."""

    idea: Idea
    passed: bool
    score: float = Field(ge=0.0, le=10.0)
    reject_reason: RejectReason | None = None
    reasoning: str = ""

    # Individual criterion scores (each 0–10)
    has_existing_spending: float = 0.0
    has_clear_buyer: float = 0.0
    mvp_feasible_24h: float = 0.0
    sells_without_brand: float = 0.0


# ---------------------------------------------------------------------------
# Layer 4: MVP Builder output
# ---------------------------------------------------------------------------


MVPFormat = Literal[
    "landing_page",
    "telegram_bot",
    "google_form_manual",
    "api_wrapper",
]


class MVPPlan(BaseModel):
    """A concrete MVP plan ready for execution."""

    filter_result: FilterResult

    @computed_field
    @property
    def idea(self) -> Idea:
        return self.filter_result.idea

    format: MVPFormat
    title: str
    tagline: str
    revenue_model: str
    price_point: str
    estimated_build_time: str
    validation_steps: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    template: str = Field(
        default="",
        description="Starter template / scaffold code or copy for the chosen format.",
    )
    deployed_url: str = Field(
        default="",
        description="Live URL after deployment. Injected into distribution posts.",
    )


# ---------------------------------------------------------------------------
# Layer 5: Manual Fulfillment output
# ---------------------------------------------------------------------------


class FulfillmentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SIMULATED = "simulated"
    FAILED = "failed"


class FulfillmentResult(BaseModel):
    """Outcome of executing (or simulating) the MVP service for a lead."""

    plan: MVPPlan
    status: FulfillmentStatus
    output: str = Field(
        default="",
        description="The delivered service output — copy, report, or simulation text.",
    )
    notes: str = Field(
        default="",
        description="Internal notes on how the fulfillment was performed.",
    )
    simulated: bool = Field(
        default=False,
        description="True when the output was produced by an LLM simulation rather than real work.",
    )


# ---------------------------------------------------------------------------
# Layer 6: Distribution Injection output
# ---------------------------------------------------------------------------


class DistributionPlatform(str, Enum):
    REDDIT = "reddit"
    INDIEHACKERS = "indiehackers"
    TWITTER = "twitter"
    TELEGRAM = "telegram"


class DistributionPost(BaseModel):
    """A platform-specific post generated for a single MVP plan."""

    platform: DistributionPlatform
    tracking_id: str = Field(
        ...,
        description="Unique ID used to correlate conversion events back to this post.",
    )
    title: str = Field(default="", description="Post title (used on Reddit / IndieHackers).")
    body: str = Field(..., description="Full post body in problem→solution→demo→CTA format.")
    cta: str = Field(..., description="Call-to-action text appended at the end of the post.")
    url: str = Field(default="", description="URL of the published post once it is live.")
    posted: bool = False
    posted_at: datetime | None = None


class DistributionResult(BaseModel):
    """All posts generated for a single MVP plan."""

    plan: MVPPlan
    posts: list[DistributionPost] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Layer 7: Conversion Tracking
# ---------------------------------------------------------------------------


class ConversionEventType(str, Enum):
    CLICK = "click"
    SIGNUP = "signup"
    REPLY = "reply"
    PAYMENT = "payment"


class ConversionEvent(BaseModel):
    """A single tracked conversion event linked to a distribution post."""

    tracking_id: str = Field(
        ...,
        description="Matches the tracking_id of the originating DistributionPost.",
    )
    event_type: ConversionEventType
    platform: DistributionPlatform
    value: float = Field(
        default=0.0,
        description="Monetary value in USD, only meaningful for payment events.",
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)


class ConversionSummary(BaseModel):
    """Aggregated conversion metrics for a single distribution post."""

    tracking_id: str
    platform: DistributionPlatform
    clicks: int = 0
    signups: int = 0
    replies: int = 0
    payments: int = 0
    total_revenue: float = 0.0
