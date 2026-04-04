"""Job boards signal miner.

Two active sources (all free, no auth required):

  1. Hacker News "Ask HN: Who is hiring?" — latest monthly thread via
     HN Algolia search API + Firebase item API.
  2. RemoteOK API — https://remoteok.com/api (JSON, no auth).

Signals are scored based on keywords that indicate recurring pain,
existing spend behaviour, or automation opportunity.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx

from src.models import PainSignal, SignalSource
from src.signal_miner.base import BaseSignalMiner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared scoring regex
# ---------------------------------------------------------------------------

_VALUE_RE = re.compile(
    r"(weekly|monthly|recurring|ongoing|every (day|week|month)|automate|automation|"
    r"save time|script|integration|workflow|\$\d+|per hour|budget|long.?term|"
    r"contract|full.?time|regular basis|repeat)",
    re.IGNORECASE,
)

_BASE_SCORE = 6.5
_VALUE_BONUS = 2.0


def _score(text: str) -> float:
    return _BASE_SCORE + (_VALUE_BONUS if _VALUE_RE.search(text) else 0.0)


# ---------------------------------------------------------------------------
# Source 1 — Hacker News "Ask HN: Who is hiring?"
# ---------------------------------------------------------------------------

_HN_ALGOLIA = (
    "https://hn.algolia.com/api/v1/search"
    "?query=Ask+HN%3A+Who+is+hiring%3F&tags=ask_hn&hitsPerPage=3"
)
_HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


async def _fetch_hn_signals(client: httpx.AsyncClient, limit: int) -> list[PainSignal]:
    """Fetch job comments from the latest HN 'Who is hiring?' thread."""
    signals: list[PainSignal] = []
    try:
        resp = await client.get(_HN_ALGOLIA)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            logger.warning("HN Algolia: no 'Who is hiring?' thread found.")
            return signals

        thread_id = hits[0]["objectID"]
        thread_resp = await client.get(_HN_ITEM.format(thread_id))
        thread_resp.raise_for_status()
        thread = thread_resp.json()
        kid_ids: list[int] = (thread.get("kids") or [])[:limit]

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
                return PainSignal(
                    source=SignalSource.JOBBOARDS,
                    source_url=f"https://news.ycombinator.com/item?id={kid_id}",
                    who_is_complaining="Company hiring on HN",
                    what_they_want=first_line,
                    current_workaround=text[len(first_line):300].strip() or "Hiring a specialist",
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
# Source 2 — RemoteOK API
# ---------------------------------------------------------------------------

_REMOTEOK_URL = "https://remoteok.com/api"


async def _fetch_remoteok_signals(client: httpx.AsyncClient, limit: int) -> list[PainSignal]:
    """Fetch job postings from the RemoteOK public API."""
    signals: list[PainSignal] = []
    try:
        resp = await client.get(
            _REMOTEOK_URL,
            headers={"User-Agent": "MoneymakerBot/1.0 (signal research)"},
        )
        resp.raise_for_status()
        jobs = resp.json()
        # First element is a legal disclaimer object — skip it
        if jobs and isinstance(jobs[0], dict) and "legal" in jobs[0]:
            jobs = jobs[1:]

        for job in jobs[:limit]:
            position = job.get("position", "")
            company = job.get("company", "Unknown")
            description = re.sub(r"<[^>]+>", " ", job.get("description") or "").strip()
            tags = ", ".join(job.get("tags") or [])
            salary_min = job.get("salary_min") or 0
            salary_max = job.get("salary_max") or 0
            url = job.get("url") or _REMOTEOK_URL

            raw = f"{position} at {company} | tags: {tags} | {description[:400]}"
            base = _score(raw)
            if salary_min > 0 or salary_max > 0:
                base = min(10.0, base + 1.0)

            salary_str = f" | ${salary_min}–${salary_max}/yr" if (salary_min or salary_max) else ""

            signals.append(
                PainSignal(
                    source=SignalSource.JOBBOARDS,
                    source_url=url,
                    who_is_complaining=f"Company hiring remotely ({company})",
                    what_they_want=f"{position}{salary_str}",
                    current_workaround=description[:300] or "Hiring a remote specialist",
                    raw_text=raw,
                    score=base,
                )
            )

        logger.info("RemoteOK miner: found %d signals.", len(signals))

    except Exception as exc:
        logger.error("RemoteOK miner error: %s", exc)

    return signals[:limit]


# ---------------------------------------------------------------------------
# JobBoardsSignalMiner
# ---------------------------------------------------------------------------


class JobBoardsSignalMiner(BaseSignalMiner):
    """Mines job board postings for recurring-pain signals.

    Fetches from two sources concurrently:
      - Hacker News "Ask HN: Who is hiring?" (monthly thread)
      - RemoteOK API
    """

    async def mine(self) -> list[PainSignal]:
        if self.dry_run:
            return self._mock_signals("jobboards", min(self.limit, 3))

        per_source = max(1, self.limit // 2)

        async with httpx.AsyncClient(timeout=15.0) as client:
            hn, remoteok = await asyncio.gather(
                _fetch_hn_signals(client, per_source),
                _fetch_remoteok_signals(client, per_source),
                return_exceptions=True,
            )

        signals: list[PainSignal] = []
        for result, name in ((hn, "HN"), (remoteok, "RemoteOK")):
            if isinstance(result, BaseException):
                logger.error("JobBoardsSignalMiner source %s raised: %s", name, result)
            else:
                signals.extend(result)

        signals.sort(key=lambda s: s.score, reverse=True)
        logger.info("JobBoardsSignalMiner: %d total signals collected.", len(signals))
        return signals[: self.limit]
