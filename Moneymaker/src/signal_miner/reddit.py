"""Reddit signal miner.

Uses the PRAW library to search multiple subreddits for posts that express
pain, requests, or frustration.  Each post is scored heuristically and
converted into a ``PainSignal``.

Requires environment variables:
    REDDIT_CLIENT_ID
    REDDIT_CLIENT_SECRET
    REDDIT_USER_AGENT
"""

from __future__ import annotations

import logging
import re

import praw
from praw.models import Submission

from src.config import settings
from src.models import PainSignal, SignalSource
from src.signal_miner.base import BaseSignalMiner

logger = logging.getLogger(__name__)

# Subreddits rich in pain / problem signals
_SUBREDDITS = [
    "entrepreneur",
    "smallbusiness",
    "SaaS",
    "freelance",
    "startups",
    "digitalnomad",
    "productivity",
    "nocode",
]

# Phrases that raise signal score
_HIGH_SIGNAL_PHRASES = [
    r"\bhow do i\b",
    r"\bpaying for\b",
    r"\btired of\b",
    r"\bannoying\b",
    r"\bfrustrating\b",
    r"\bwaste.{0,10}time\b",
    r"\bnobody.{0,15}built\b",
    r"\bwish there was\b",
    r"\bneed a tool\b",
    r"\bcan\'t find\b",
    r"\btoo expensive\b",
    r"\balternative to\b",
    r"\bpain point\b",
    r"\bhow much do you pay\b",
    r"\bbudget for\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _HIGH_SIGNAL_PHRASES]


def _score_post(text: str) -> float:
    """Return a 0–10 heuristic score based on pain-signal phrase density."""
    hits = sum(1 for pat in _COMPILED if pat.search(text))
    return min(10.0, hits * 1.5 + 3.0)


def _post_to_signal(post: Submission) -> PainSignal:
    full_text = f"{post.title}\n{post.selftext or ''}"
    score = _score_post(full_text)
    return PainSignal(
        source=SignalSource.REDDIT,
        source_url=f"https://reddit.com{post.permalink}",
        who_is_complaining="Reddit user in r/" + post.subreddit.display_name,
        what_they_want=post.title[:300],
        current_workaround=post.selftext[:300] if post.selftext else "Unknown",
        raw_text=full_text[:2000],
        score=score,
    )


class RedditSignalMiner(BaseSignalMiner):
    """Mines pain signals from a curated set of entrepreneurship subreddits."""

    async def mine(self) -> list[PainSignal]:
        if self.dry_run:
            return self._mock_signals("reddit", min(self.limit, 3))

        if not settings.reddit_client_id or not settings.reddit_client_secret:
            logger.warning("Reddit credentials not configured – skipping Reddit miner.")
            return []

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

        subreddit_str = "+".join(_SUBREDDITS)
        subreddit = reddit.subreddit(subreddit_str)

        search_queries = [
            "how do I automate",
            "wish there was a tool",
            "too expensive alternative",
            "paying for help",
            "anyone built",
        ]

        signals: list[PainSignal] = []
        seen: set[str] = set()

        for query in search_queries:
            if len(signals) >= self.limit:
                break
            try:
                for post in subreddit.search(query, sort="new", limit=20):
                    if post.id in seen:
                        continue
                    seen.add(post.id)
                    signal = _post_to_signal(post)
                    if signal.score >= settings.signal_min_score:
                        signals.append(signal)
                    if len(signals) >= self.limit:
                        break
            except Exception as exc:  # pragma: no cover
                logger.error("Reddit search error for query '%s': %s", query, exc)

        logger.info("RedditSignalMiner: found %d signals.", len(signals))
        return signals[: self.limit]
