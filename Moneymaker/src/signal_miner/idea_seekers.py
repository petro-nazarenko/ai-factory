"""Idea Seekers signal miner.

Targets non-technical founders and people with startup ideas who are actively
looking for a developer or no-code solution. These are our primary customers —
people who have validated the idea in their head but can't execute without help.

Searches: r/entrepreneur, r/startups, r/SaaS

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

_SUBREDDITS = [
    "entrepreneur",
    "startups",
    "SaaS",
]

# Queries that surface non-technical founders seeking builders / solutions
_SEARCH_QUERIES = [
    "I have an idea but can't code",
    "looking for developer for my idea",
    "how do I build my startup idea",
    "non-technical founder",
    "no code solution for",
    "wish someone would build",
]

# Base scoring: phrase density on general pain signals
_PAIN_PHRASES = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bcan\'?t code\b",
        r"\bnon.?technical\b",
        r"\blooking for (a )?developer\b",
        r"\bwish someone (would|could) build\b",
        r"\bhow do i build\b",
        r"\bno.?code\b",
        r"\bneed (a )?co.?founder\b",
        r"\bfind (a )?developer\b",
        r"\boutsource\b",
        r"\bupwork\b",
        r"\bfiverr\b",
    ]
]

# Bonus scoring: signals that indicate budget / willingness to pay
_BUDGET_PHRASES = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bbudget\b",
        r"\bpaying\b",
        r"\bwilling to pay\b",
        r"\bhire\b",
        r"\bcontract\b",
        r"\bequity\b",
        r"\b\$\d+\b",
        r"\bper (hour|month|project)\b",
        r"\bpaid\b",
        r"\bcompensation\b",
    ]
]

_BASE_SCORE = 5.0
_PAIN_HIT = 1.2   # per matched pain phrase
_BUDGET_BONUS = 2.0  # flat bonus when any budget signal found


def _score_post(text: str) -> float:
    pain_hits = sum(1 for pat in _PAIN_PHRASES if pat.search(text))
    has_budget = any(pat.search(text) for pat in _BUDGET_PHRASES)
    score = _BASE_SCORE + pain_hits * _PAIN_HIT + (_BUDGET_BONUS if has_budget else 0.0)
    return min(10.0, score)


def _post_to_signal(post: Submission) -> PainSignal:
    full_text = f"{post.title}\n{post.selftext or ''}"
    score = _score_post(full_text)
    subreddit = post.subreddit.display_name
    author = str(post.author) if post.author else "unknown"
    return PainSignal(
        source=SignalSource.IDEA_SEEKERS,
        source_url=f"https://reddit.com{post.permalink}",
        source_author=author,
        source_company="",
        source_text=full_text,
        posted_date="",
        who_is_complaining=f"Non-technical founder on r/{subreddit} (@{author})",
        what_they_want=post.title[:300],
        current_workaround=(post.selftext[:300].strip() if post.selftext else "Not specified"),
        raw_text=full_text[:2000],
        score=score,
    )


class IdeaSeekersSignalMiner(BaseSignalMiner):
    """Mines signals from non-technical founders actively seeking builders or no-code solutions.

    These are direct customers: people with budgets who need someone to build for them.
    """

    async def mine(self) -> list[PainSignal]:
        if self.dry_run:
            return self._mock_idea_seeker_signals(min(self.limit, 3))

        if not settings.reddit_client_id or not settings.reddit_client_secret:
            logger.warning("Reddit credentials not configured – skipping IdeaSeekersSignalMiner.")
            return []

        reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )

        subreddit_str = "+".join(_SUBREDDITS)
        subreddit = reddit.subreddit(subreddit_str)

        signals: list[PainSignal] = []
        seen: set[str] = set()

        for query in _SEARCH_QUERIES:
            if len(signals) >= self.limit:
                break
            try:
                for post in subreddit.search(query, sort="new", limit=25):
                    if post.id in seen:
                        continue
                    seen.add(post.id)
                    signal = _post_to_signal(post)
                    if signal.score >= settings.signal_min_score:
                        signals.append(signal)
                    if len(signals) >= self.limit:
                        break
            except Exception as exc:
                logger.error("IdeaSeekersSignalMiner search error for query %r: %s", query, exc)

        # Sort so budget-signalling posts surface first
        signals.sort(key=lambda s: s.score, reverse=True)
        logger.info("IdeaSeekersSignalMiner: found %d signals.", len(signals))
        return signals[: self.limit]

    @staticmethod
    def _mock_idea_seeker_signals(count: int) -> list[PainSignal]:
        templates = [
            {
                "source_author": "mock_user1",
                "source_url": "https://reddit.com/r/entrepreneur/mock1",
                "who_is_complaining": "Non-technical founder on r/entrepreneur (@mock_user1)",
                "what_they_want": "I have an idea but can't code — willing to pay or offer equity",
                "current_workaround": "Tried no-code tools but hit limitations. Have $5k budget.",
                "raw_text": "[mock:idea_seekers] I have a validated idea for a SaaS, can't code, budget $5k, looking for developer",
                "score": 9.0,
            },
            {
                "source_author": "mock_user2",
                "source_url": "https://reddit.com/r/startups/mock2",
                "who_is_complaining": "Non-technical founder on r/startups (@mock_user2)",
                "what_they_want": "Looking for developer for my startup idea — paying project rate",
                "current_workaround": "Posted on Upwork but quality was bad. Need someone serious.",
                "raw_text": "[mock:idea_seekers] Non-technical founder here, looking to hire developer for MVP, paying hourly",
                "score": 8.5,
            },
            {
                "source_author": "mock_user3",
                "source_url": "https://reddit.com/r/SaaS/mock3",
                "who_is_complaining": "Non-technical founder on r/SaaS (@mock_user3)",
                "what_they_want": "Wish someone would build a tool to automate my invoicing workflow",
                "current_workaround": "Using spreadsheets. Would pay $50/mo for a real solution.",
                "raw_text": "[mock:idea_seekers] Wish someone would build a simple invoicing automation, would pay monthly",
                "score": 7.5,
            },
        ]
        return [
            PainSignal(source=SignalSource.IDEA_SEEKERS, source_company="", source_text=t["raw_text"], posted_date="", **{k: v for k, v in t.items() if k not in ("source_text",)})
            for t in templates[:count]
        ]
