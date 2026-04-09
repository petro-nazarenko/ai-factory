"""Pain signal miner — HN + Reddit.

Two sources focused on *expressed problems*, not hiring needs:

  1. Hacker News "Ask HN: What are you working on?" — latest monthly thread.
     Builders describe what they're building and why existing tools fail them.

  2. Reddit r/entrepreneur + r/SaaS + r/smallbusiness — posts asking
     "how do you handle X" or "looking for a tool to automate Y".
     Uses the Reddit OAuth2 client-credentials flow (no user login required).
     Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET in env / .env

Signals are scored based on keywords that indicate recurring pain,
existing spend behaviour, or automation opportunity.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from datetime import datetime, timezone

import httpx

from src.config import settings
from src.models import PainSignal, SignalSource
from src.signal_miner.base import BaseSignalMiner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared scoring
# ---------------------------------------------------------------------------

_VALUE_RE = re.compile(
    r"(weekly|monthly|recurring|ongoing|every (day|week|month)|automate|automation|"
    r"save time|script|integration|workflow|\$\d+|per hour|budget|long.?term|"
    r"contract|full.?time|regular basis|repeat)",
    re.IGNORECASE,
)

_PAIN_RE = re.compile(
    r"(how do (i|you|we)\b|looking for (a )?tool|wish there was|"
    r"can.t find|nobody built|need to automate|pain point|frustrat|"
    r"waste.{0,10}time|too manual|spreadsheet hell|no good solution|"
    r"any tool (that|to)|alternative to|tired of|annoying)",
    re.IGNORECASE,
)

_BASE_SCORE = 6.0
_VALUE_BONUS = 1.5
_PAIN_BONUS = 2.0


def _score(text: str) -> float:
    s = _BASE_SCORE
    if _VALUE_RE.search(text):
        s += _VALUE_BONUS
    if _PAIN_RE.search(text):
        s += _PAIN_BONUS
    return min(10.0, s)


# ---------------------------------------------------------------------------
# Source 1 — HN "Ask HN: What are you working on?"
# ---------------------------------------------------------------------------

_HN_ALGOLIA = "https://hn.algolia.com/api/v1/search_by_date"
_HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


async def _fetch_hn_signals(client: httpx.AsyncClient, limit: int) -> list[PainSignal]:
    """Fetch pain signals from the latest 'Ask HN: What are you working on?' thread."""
    signals: list[PainSignal] = []
    try:
        resp = await client.get(
            _HN_ALGOLIA,
            params={"query": "Ask HN: What are you working on?", "tags": "ask_hn", "hitsPerPage": "5"},
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            logger.warning("HN Algolia: no 'What are you working on?' thread found.")
            return signals

        latest = max(hits, key=lambda h: h.get("created_at_i", 0))
        thread_id = latest["objectID"]
        logger.info("HN miner: thread id=%s created=%s", thread_id, latest.get("created_at"))

        thread_resp = await client.get(_HN_ITEM.format(thread_id))
        thread_resp.raise_for_status()
        kid_ids: list[int] = (thread_resp.json().get("kids") or [])[:limit]

        async def fetch_comment(kid_id: int) -> PainSignal | None:
            try:
                r = await client.get(_HN_ITEM.format(kid_id))
                r.raise_for_status()
                item = r.json()
                text = re.sub(r"<[^>]+>", " ", item.get("text") or "").strip()
                if not text or item.get("dead") or item.get("deleted"):
                    return None
                raw = text[:600]
                first_line = text.split("\n")[0][:200]

                # Extract the problem they're solving
                pain_match = re.search(
                    r"(?:because|problem[:\s]|pain[:\s]|couldn.t find|"
                    r"needed to|frustrat|manual|no tool|built because|"
                    r"existing tools|tired of|wish there was)(.{10,250})",
                    text, re.IGNORECASE,
                )
                pain_context = pain_match.group(0)[:250].strip() if pain_match else first_line

                author = item.get("by", "")
                unix_ts = item.get("time", 0)
                posted_date = (
                    datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if unix_ts else ""
                )
                return PainSignal(
                    source=SignalSource.JOBBOARDS,
                    source_url=f"https://news.ycombinator.com/item?id={kid_id}",
                    source_author=author,
                    source_company="",
                    source_text=text,
                    posted_date=posted_date,
                    who_is_complaining=f"Builder on HN (@{author})" if author else "Builder on HN",
                    what_they_want=first_line,
                    current_workaround=pain_context,
                    raw_text=raw,
                    score=_score(raw),
                )
            except Exception as exc:
                logger.debug("HN comment fetch error for %s: %s", kid_id, exc)
                return None

        results = await asyncio.gather(*[fetch_comment(k) for k in kid_ids])
        signals = [s for s in results if s is not None]
        logger.info("HN miner: found %d signals.", len(signals))

    except Exception as exc:
        logger.error("HN miner error: %s", exc)

    return signals[:limit]


# ---------------------------------------------------------------------------
# Source 2 — Reddit pain signals (OAuth2 client credentials)
# ---------------------------------------------------------------------------

_REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_REDDIT_SEARCH_URL = "https://oauth.reddit.com/r/{subs}/search"
_REDDIT_SUBREDDITS = "entrepreneur+SaaS+smallbusiness"

# Queries that surface posts expressing pain / tool-seeking behaviour
_REDDIT_QUERIES = [
    "how do you handle",
    "looking for a tool to automate",
    "how do you automate",
    "wish there was a tool",
    "anyone built something",
    "too manual need to automate",
    "no good solution for",
]


async def _reddit_token(client: httpx.AsyncClient) -> str | None:
    """Obtain a Reddit app-only OAuth2 bearer token."""
    creds = base64.b64encode(
        f"{settings.reddit_client_id}:{settings.reddit_client_secret}".encode()
    ).decode()
    try:
        resp = await client.post(
            _REDDIT_TOKEN_URL,
            headers={
                "Authorization": f"Basic {creds}",
                "User-Agent": settings.reddit_user_agent,
            },
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        logger.error("Reddit token fetch failed: %s", exc)
        return None


async def _fetch_reddit_signals(client: httpx.AsyncClient, limit: int) -> list[PainSignal]:
    """Search entrepreneur/SaaS/smallbusiness for posts expressing pain or tool needs."""
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        logger.warning("Reddit credentials not set — skipping Reddit pain miner.")
        return []

    token = await _reddit_token(client)
    if not token:
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": settings.reddit_user_agent,
    }

    signals: list[PainSignal] = []
    seen: set[str] = set()
    per_query = max(1, limit // len(_REDDIT_QUERIES))

    for query in _REDDIT_QUERIES:
        if len(signals) >= limit:
            break
        try:
            resp = await client.get(
                _REDDIT_SEARCH_URL.format(subs=_REDDIT_SUBREDDITS),
                headers=headers,
                params={
                    "q": query,
                    "sort": "new",
                    "t": "month",
                    "limit": per_query * 3,  # fetch extra, filter down
                    "restrict_sr": "true",
                    "type": "link",
                },
            )
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])

            for post in posts:
                if len(signals) >= limit:
                    break
                d = post.get("data", {})
                post_id = d.get("id", "")
                if not post_id or post_id in seen:
                    continue
                seen.add(post_id)

                title = d.get("title", "")
                body = d.get("selftext", "") or ""
                full_text = f"{title}\n{body}".strip()

                # Skip link-only posts with no body
                if len(body.strip()) < 20 and not _PAIN_RE.search(title):
                    continue

                raw = full_text[:600]
                score = _score(raw)

                # Boost posts that directly ask for tools/solutions
                if re.search(r"(tool|software|app|automate|solution|script)", title, re.IGNORECASE):
                    score = min(10.0, score + 0.5)

                subreddit = d.get("subreddit", "")
                author = d.get("author", "")
                created_utc = d.get("created_utc", 0)
                posted_date = (
                    datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    if created_utc else ""
                )

                signals.append(PainSignal(
                    source=SignalSource.REDDIT,
                    source_url=f"https://reddit.com{d.get('permalink', '')}",
                    source_author=author,
                    source_company="",
                    source_text=full_text,
                    posted_date=posted_date,
                    who_is_complaining=f"r/{subreddit} user (@{author})" if author else f"r/{subreddit}",
                    what_they_want=title[:300],
                    current_workaround=body[:300].strip() or "Not specified",
                    raw_text=raw,
                    score=score,
                ))

        except Exception as exc:
            logger.error("Reddit search error for query %r: %s", query, exc)

    logger.info("Reddit pain miner: found %d signals.", len(signals))
    return signals[:limit]


# ---------------------------------------------------------------------------
# JobBoardsSignalMiner
# ---------------------------------------------------------------------------


class JobBoardsSignalMiner(BaseSignalMiner):
    """Mines pain signals from HN builders and Reddit entrepreneurs.

    Sources:
      - HN "Ask HN: What are you working on?" — builders describing problems
      - Reddit r/entrepreneur + r/SaaS + r/smallbusiness — tool-seeking posts
    """

    async def mine(self) -> list[PainSignal]:
        if self.dry_run:
            return self._mock_signals("jobboards", min(self.limit, 3))

        per_source = max(1, self.limit // 2)

        async with httpx.AsyncClient(timeout=20.0) as client:
            hn, reddit = await asyncio.gather(
                _fetch_hn_signals(client, per_source),
                _fetch_reddit_signals(client, per_source),
                return_exceptions=True,
            )

        signals: list[PainSignal] = []
        for result, name in ((hn, "HN"), (reddit, "Reddit")):
            if isinstance(result, BaseException):
                logger.error("JobBoardsSignalMiner source %s raised: %s", name, result)
            else:
                signals.extend(result)

        signals.sort(key=lambda s: s.score, reverse=True)
        logger.info("JobBoardsSignalMiner: %d total signals collected.", len(signals))
        return signals[: self.limit]
