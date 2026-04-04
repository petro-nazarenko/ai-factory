"""Pipeline 2 — Client Finder.

Scans HN "Ask HN: Who is hiring?" threads for cloud/infra/devops pain signals.
Extracts company name, contact, and pain description.

Output: workspace/leads/leads.json

Usage:
    python workspace/client_finder.py [--limit N] [--dry-run] [--output PATH]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HN API endpoints (same as jobboards.py)
# ---------------------------------------------------------------------------

_HN_ALGOLIA = (
    "https://hn.algolia.com/api/v1/search"
    "?query=Ask+HN%3A+Who+is+hiring%3F&tags=ask_hn&hitsPerPage=3"
)
_HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"

# ---------------------------------------------------------------------------
# Target keyword filters
# ---------------------------------------------------------------------------

_INFRA_RE = re.compile(
    r"\b(cloud|AWS|Azure|GCP|Google Cloud|infrastructure|infra|"
    r"cost|optim|devops|dev ops|monitoring|observability|"
    r"kubernetes|k8s|terraform|ansible|CI/CD|pipeline|deploy|"
    r"reliability|SRE|platform engineering)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_COMPANY_PATTERNS = [
    # "We are FooBar," / "At FooBar," / "FooBar is hiring"
    re.compile(r"(?:We(?:'re| are) |At |joining )([A-Z][A-Za-z0-9 &.,'-]{2,40}?)(?:[,.]| —| –| is | are )", re.MULTILINE),
    # "FooBar | Remote" (common HN hiring format)
    re.compile(r"^([A-Z][A-Za-z0-9 &.,'-]{2,40}?)\s*[\|│]", re.MULTILINE),
    # "Company: FooBar"
    re.compile(r"[Cc]ompany:\s*([A-Za-z0-9 &.,'-]{2,40})", re.MULTILINE),
]

_STRIP_HTML_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _STRIP_HTML_RE.sub(" ", text).strip()


def _extract_company(text: str) -> str:
    for pattern in _COMPANY_PATTERNS:
        m = pattern.search(text)
        if m:
            candidate = m.group(1).strip().strip(".,")
            if 2 < len(candidate) < 60:
                return candidate
    return "Unknown"


def _extract_contact(text: str, by_user: str | None) -> str:
    email_match = _EMAIL_RE.search(text)
    if email_match:
        return email_match.group(0)
    if by_user:
        return f"https://news.ycombinator.com/user?id={by_user}"
    return "Unknown"


def _extract_pain(text: str) -> str:
    """Pull the first sentence / clause that mentions an infra keyword."""
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    for sent in sentences:
        if _INFRA_RE.search(sent):
            return sent.strip()[:300]
    # Fallback: first 200 chars of matching text
    return text[:200]


def _score_lead(text: str) -> int:
    """Score 0-10 based on density and urgency of infra pain signals."""
    matches = _INFRA_RE.findall(text)
    keyword_count = len(matches)

    score = min(keyword_count * 2, 6)  # up to 6 from keyword density

    urgency_re = re.compile(
        r"(urgent|immediately|asap|critical|struggling|pain|expensive|"
        r"cost overrun|over budget|alert fatigue|downtime|incident)",
        re.IGNORECASE,
    )
    if urgency_re.search(text):
        score += 2

    spend_re = re.compile(r"(\$\d+|\d+k|\d+ k|budget|saving|reduce cost)", re.IGNORECASE)
    if spend_re.search(text):
        score += 2

    return min(score, 10)


# ---------------------------------------------------------------------------
# Mock data for --dry-run
# ---------------------------------------------------------------------------

_MOCK_LEADS = [
    {
        "company": "Acme Cloud Co",
        "contact": "founder@acme.io",
        "pain": "We're spending too much on AWS and need cost optimization across our ECS/RDS stack.",
        "hn_url": "https://news.ycombinator.com/item?id=99999991",
        "score": 8,
    },
    {
        "company": "DataFlow Inc",
        "contact": "https://news.ycombinator.com/user?id=dfcto",
        "pain": "Looking for DevOps engineer to own our GCP infrastructure and monitoring stack.",
        "hn_url": "https://news.ycombinator.com/item?id=99999992",
        "score": 7,
    },
    {
        "company": "ScaleOps",
        "contact": "jobs@scaleops.dev",
        "pain": "Kubernetes cluster costs spiraling — need someone to own observability and cost controls.",
        "hn_url": "https://news.ycombinator.com/item?id=99999993",
        "score": 9,
    },
]


# ---------------------------------------------------------------------------
# Core async fetch
# ---------------------------------------------------------------------------

async def _fetch_comment(client: httpx.AsyncClient, kid_id: int) -> dict | None:
    try:
        r = await client.get(_HN_ITEM.format(kid_id))
        r.raise_for_status()
        item = r.json()
        if not item or item.get("dead") or item.get("deleted"):
            return None
        raw_text = _strip_html(item.get("text") or "")
        if not raw_text:
            return None
        return {
            "id": kid_id,
            "by": item.get("by"),
            "text": raw_text,
        }
    except Exception as exc:
        logger.debug("Comment fetch error %s: %s", kid_id, exc)
        return None


async def fetch_leads(limit: int = 50) -> list[dict]:
    leads: list[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Find latest "Who is hiring?" thread
        resp = await client.get(_HN_ALGOLIA)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            logger.error("No 'Who is hiring?' thread found via Algolia.")
            return leads

        thread_id = hits[0]["objectID"]
        thread_url = f"https://news.ycombinator.com/item?id={thread_id}"
        logger.info("Using thread: %s", thread_url)

        thread_resp = await client.get(_HN_ITEM.format(thread_id))
        thread_resp.raise_for_status()
        thread = thread_resp.json()
        kid_ids: list[int] = (thread.get("kids") or [])[:limit * 3]  # fetch more, filter down

        logger.info("Fetching %d comments...", len(kid_ids))
        comments = await asyncio.gather(*[_fetch_comment(client, k) for k in kid_ids])

    # 2. Filter and extract
    for comment in comments:
        if comment is None:
            continue
        text = comment["text"]
        if not _INFRA_RE.search(text):
            continue

        company = _extract_company(text)
        contact = _extract_contact(text, comment.get("by"))
        pain = _extract_pain(text)
        score = _score_lead(text)
        hn_url = f"https://news.ycombinator.com/item?id={comment['id']}"

        leads.append({
            "company": company,
            "contact": contact,
            "pain": pain,
            "hn_url": hn_url,
            "score": score,
        })

    leads.sort(key=lambda x: x["score"], reverse=True)
    logger.info("Client Finder: %d leads matched infra/cloud filter.", len(leads))
    return leads[:limit]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Client Finder — HN infra/cloud lead extractor")
    parser.add_argument("--limit", type=int, default=50, help="Max leads to return (default: 50)")
    parser.add_argument("--output", type=str, default="workspace/leads/leads.json",
                        help="Output file path (default: workspace/leads/leads.json)")
    parser.add_argument("--dry-run", action="store_true", help="Use mock data, no external calls")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        logger.info("DRY RUN — using mock leads.")
        leads = _MOCK_LEADS
    else:
        leads = asyncio.run(fetch_leads(limit=args.limit))

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)

    logger.info("Wrote %d leads → %s", len(leads), output_path)

    # Print summary
    print(f"\n{'─'*50}")
    print(f"  Leads found : {len(leads)}")
    print(f"  Output      : {output_path}")
    if leads:
        top = leads[0]
        print(f"  Top lead    : {top['company']} (score {top['score']}/10)")
        print(f"  Contact     : {top['contact']}")
    print(f"{'─'*50}\n")


if __name__ == "__main__":
    main()
