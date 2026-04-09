"""Distribution Injection — Layer 6 of the MVP Idea Engine.

Generates platform-specific posts for each MVP plan and (optionally) publishes
them via their respective APIs.  Each post follows the canonical format::

    Problem → Solution → Demo → CTA

Each post receives a unique ``tracking_id`` (UUID) so that conversion events
can be correlated back to the originating post and platform.

Supported platforms
-------------------
- **reddit**       – posts to a relevant subreddit via the Reddit API (PRAW)
- **indiehackers** – posts a "Show IH" thread (API posting not officially
                     supported; content is generated for manual posting or
                     future automation)
- **twitter**      – posts a thread of up to 5 tweets via the Twitter v2 API
- **telegram**     – sends a message to a Telegram channel via Bot API

In ``dry_run=True`` mode (or when credentials are absent), content is
generated but not published; ``posted`` remains ``False``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from textwrap import dedent

import httpx

from src.config import settings
from src.models import (
    DistributionPlatform,
    DistributionPost,
    DistributionResult,
    MVPPlan,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Post format helpers
# ---------------------------------------------------------------------------

_REDDIT_TEMPLATE = dedent(
    """
    **Problem:** {problem}

    **Solution:** {title} — {tagline}

    **Demo:** {demo}

    ---

    {cta}
    """
).strip()

_IH_TEMPLATE = dedent(
    """
    ## The Problem

    {problem}

    ## What I Built

    {title} — {tagline}

    {solution}

    ## Demo / Early Results

    {demo}

    ---

    {cta}
    """
).strip()

_TWITTER_TEMPLATE = dedent(
    """
    🧵 {problem}

    👇 Here's what I did about it:

    {title} — {tagline}

    {solution}

    🎯 {demo}

    {cta}
    """
).strip()

_TELEGRAM_TEMPLATE = dedent(
    """
    🔥 *{title}* — {tagline}

    *Problem:* {problem}

    *Solution:* {solution}

    *Demo:* {demo}

    {cta}
    """
).strip()

_TEMPLATES: dict[DistributionPlatform, str] = {
    DistributionPlatform.REDDIT: _REDDIT_TEMPLATE,
    DistributionPlatform.INDIEHACKERS: _IH_TEMPLATE,
    DistributionPlatform.TWITTER: _TWITTER_TEMPLATE,
    DistributionPlatform.TELEGRAM: _TELEGRAM_TEMPLATE,
}

# Default demo snippet when no URL is set
_DEFAULT_DEMO = (
    "I manually fulfilled the first order in under 2 hours "
    "and the customer was happy to pay."
)


def _build_cta(plan: MVPPlan) -> str:
    url_part = f"\n👉 {plan.deployed_url}" if plan.deployed_url else ""
    return (
        f"💸 {plan.revenue_model} — starting at {plan.price_point}. "
        f"DM me or drop your email below if you want early access.{url_part}"
    )


def _build_demo(plan: MVPPlan) -> str:
    if plan.validation_steps:
        return plan.validation_steps[0]
    return _DEFAULT_DEMO


def _esc(s: str) -> str:
    """Escape curly braces in user-generated content before str.format()."""
    return s.replace("{", "{{").replace("}", "}}")


def _generate_post(plan: MVPPlan, platform: DistributionPlatform) -> DistributionPost:
    """Create a DistributionPost for *plan* on *platform*."""
    tracking_id = uuid.uuid4().hex
    cta = _build_cta(plan)
    demo = _build_demo(plan)

    template = _TEMPLATES[platform]
    body = template.format(
        problem=_esc(plan.idea.problem),
        title=_esc(plan.title),
        tagline=_esc(plan.tagline),
        solution=_esc(plan.idea.solution),
        demo=_esc(demo),
        cta=_esc(cta),
    )

    title = f"{plan.title} — {plan.tagline}"

    return DistributionPost(
        platform=platform,
        tracking_id=tracking_id,
        title=title,
        body=body,
        cta=cta,
    )


# ---------------------------------------------------------------------------
# Platform publishers (live mode)
# ---------------------------------------------------------------------------


async def _post_reddit(post: DistributionPost, plan: MVPPlan) -> DistributionPost:
    """Publish to Reddit using PRAW (synchronous lib wrapped in executor)."""
    import asyncio

    if not (settings.reddit_client_id and settings.reddit_client_secret):
        logger.warning("Reddit credentials missing — skipping Reddit post.")
        return post

    def _submit() -> str:
        import praw  # type: ignore[import]

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        # Pick a sensible sub based on the plan format
        subreddit_name = settings.reddit_distribution_subreddit or "indiehackers"
        submission = reddit.subreddit(subreddit_name).submit(
            title=post.title,
            selftext=post.body,
        )
        return f"https://reddit.com{submission.permalink}"

    try:
        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(None, _submit)
        return post.model_copy(update={"posted": True, "url": url})
    except Exception as exc:
        logger.error("Reddit post failed: %s", exc)
        return post


async def _post_twitter(post: DistributionPost) -> DistributionPost:
    """Post a thread to Twitter/X via the v2 API."""
    if not settings.twitter_bearer_token:
        logger.warning("Twitter bearer token missing — skipping Twitter post.")
        return post

    # Split body into ≤280-char chunks for a thread
    chunks: list[str] = []
    remaining = post.body
    while remaining:
        if len(remaining) <= 280:
            chunks.append(remaining)
            break
        split_at = remaining.rfind(" ", 0, 277)
        if split_at == -1:
            split_at = 277
        chunks.append(remaining[:split_at] + "…")
        remaining = remaining[split_at:].lstrip()

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {settings.twitter_bearer_token}",
                "Content-Type": "application/json",
            }
            previous_id: str | None = None
            first_url = ""
            for i, chunk in enumerate(chunks):
                payload: dict = {"text": chunk}
                if previous_id:
                    payload["reply"] = {"in_reply_to_tweet_id": previous_id}
                resp = await client.post(
                    "https://api.twitter.com/2/tweets",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                tweet_id = resp.json()["data"]["id"]
                if i == 0:
                    first_url = f"https://twitter.com/i/web/status/{tweet_id}"
                previous_id = tweet_id
        return post.model_copy(update={"posted": True, "url": first_url})
    except Exception as exc:
        logger.error("Twitter post failed: %s", exc)
        return post


async def _post_telegram(post: DistributionPost) -> DistributionPost:
    """Send a message to a Telegram channel via Bot API."""
    if not (settings.telegram_bot_token and settings.telegram_channel_id):
        logger.warning("Telegram credentials missing — skipping Telegram post.")
        return post

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_channel_id,
        "text": post.body,
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            msg_id = resp.json()["result"]["message_id"]
            channel = settings.telegram_channel_id.lstrip("@")
            post_url = f"https://t.me/{channel}/{msg_id}"
        return post.model_copy(update={"posted": True, "url": post_url})
    except Exception as exc:
        logger.error("Telegram post failed: %s", exc)
        return post


async def _publish_post(post: DistributionPost, plan: MVPPlan) -> DistributionPost:
    """Dispatch to the right publisher."""
    if post.platform == DistributionPlatform.REDDIT:
        return await _post_reddit(post, plan)
    if post.platform == DistributionPlatform.TWITTER:
        return await _post_twitter(post)
    if post.platform == DistributionPlatform.TELEGRAM:
        return await _post_telegram(post)
    # IndieHackers: no official API — content generated only
    logger.info(
        "IndieHackers: post content generated (manual posting required). "
        "tracking_id=%s",
        post.tracking_id,
    )
    return post


# ---------------------------------------------------------------------------
# Public Distributor class
# ---------------------------------------------------------------------------

_ALL_PLATFORMS = [p for p in DistributionPlatform]


class Distributor:
    """Generates and (optionally) publishes platform posts for MVP plans."""

    def __init__(
        self,
        dry_run: bool = False,
        platforms: list[str] | None = None,
    ) -> None:
        self.dry_run = dry_run
        if platforms is not None:
            self.platforms = [DistributionPlatform(p) for p in platforms]
        else:
            self.platforms = _ALL_PLATFORMS

    async def distribute(self, plan: MVPPlan) -> DistributionResult:
        """Generate posts for all configured platforms and optionally publish them."""
        posts: list[DistributionPost] = []
        for platform in self.platforms:
            post = _generate_post(plan, platform)
            if not self.dry_run:
                post = await _publish_post(post, plan)
            posts.append(post)
            logger.info(
                "Distributor: platform=%s tracking_id=%s posted=%s",
                platform.value,
                post.tracking_id,
                post.posted,
            )
        return DistributionResult(plan=plan, posts=posts)

    async def distribute_all(self, plans: list[MVPPlan]) -> list[DistributionResult]:
        """Distribute all MVP plans concurrently and return results."""
        return list(await asyncio.gather(*(self.distribute(plan) for plan in plans)))
