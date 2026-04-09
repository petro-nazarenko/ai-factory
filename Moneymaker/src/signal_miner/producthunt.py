"""Product Hunt signal miner.

Uses the Product Hunt GraphQL API to find new products whose comments / taglines
contain pain signals — especially tools that solve niche problems and have
paying customers.

Requires environment variable:
    PRODUCTHUNT_TOKEN  (Developer token from producthunt.com/v2/oauth/applications)
"""

from __future__ import annotations

import logging

import httpx

from src.config import settings
from src.models import PainSignal, SignalSource
from src.signal_miner.base import BaseSignalMiner

logger = logging.getLogger(__name__)

_PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

_POSTS_QUERY = """
query {
  posts(first: 20, order: NEWEST) {
    edges {
      node {
        id
        name
        tagline
        description
        url
        topics {
          edges {
            node { name }
          }
        }
        comments(first: 5) {
          edges {
            node { body }
          }
        }
      }
    }
  }
}
"""


def _node_to_signal(node: dict) -> PainSignal:
    comments = " | ".join(
        edge["node"]["body"]
        for edge in node.get("comments", {}).get("edges", [])
    )
    raw = f"{node['name']}: {node.get('tagline', '')}. {node.get('description', '')}. Comments: {comments}"
    return PainSignal(
        source=SignalSource.PRODUCTHUNT,
        source_url=node.get("url", ""),
        who_is_complaining="Product Hunt community / early adopters",
        what_they_want=node.get("tagline", node["name"])[:300],
        current_workaround=node.get("description", "")[:300] or "No known workaround mentioned",
        raw_text=raw[:2000],
        score=6.5,  # PH posts are pre-filtered by the community; base score 6.5
    )


class ProductHuntSignalMiner(BaseSignalMiner):
    """Mines new Product Hunt launches for pain-adjacent problems."""

    async def mine(self) -> list[PainSignal]:
        if self.dry_run:
            return self._mock_signals("producthunt", min(self.limit, 3))

        if not settings.producthunt_token:
            logger.warning("PRODUCTHUNT_TOKEN not configured – skipping Product Hunt miner.")
            return []

        headers = {
            "Authorization": f"Bearer {settings.producthunt_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _PH_GRAPHQL_URL,
                    json={"query": _POSTS_QUERY},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("Product Hunt API error: %s", exc)
            return []

        nodes = [edge["node"] for edge in data.get("data", {}).get("posts", {}).get("edges", [])]
        signals = [_node_to_signal(n) for n in nodes[: self.limit]]
        logger.info("ProductHuntSignalMiner: found %d signals.", len(signals))
        return signals
