"""IndieHackers signal miner.

Scrapes IndieHackers public forum pages for monetization and pain threads.
No API key required – uses public HTML scraping via httpx.
"""

from __future__ import annotations

import logging
import re

import httpx

from src.models import PainSignal, SignalSource
from src.signal_miner.base import BaseSignalMiner

logger = logging.getLogger(__name__)

_IH_GROUPS = [
    "https://www.indiehackers.com/group/help-wanted",
    "https://www.indiehackers.com/group/show-your-tool",
    "https://www.indiehackers.com/group/growth",
]

_TITLE_RE = re.compile(r'<a[^>]+class="[^"]*title[^"]*"[^>]*>([^<]+)</a>', re.IGNORECASE)
_PAIN_PHRASES = re.compile(
    r"(how do i|paying for|anyone else|wish|frustrated|struggling|need help|"
    r"can\'t find|too expensive|no tool|manual process|hours every week)",
    re.IGNORECASE,
)


class IndieHackersSignalMiner(BaseSignalMiner):
    """Scrapes IndieHackers forum for pain/monetization signals."""

    async def mine(self) -> list[PainSignal]:
        if self.dry_run:
            return self._mock_signals("indiehackers", min(self.limit, 3))

        signals: list[PainSignal] = []
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "MoneymakerBot/1.0"},
            follow_redirects=True,
        ) as client:
            for url in _IH_GROUPS:
                if len(signals) >= self.limit:
                    break
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    titles = _TITLE_RE.findall(resp.text)
                    for title in titles:
                        title = title.strip()
                        if not title or len(title) < 20:
                            continue
                        if not _PAIN_PHRASES.search(title):
                            continue
                        signals.append(
                            PainSignal(
                                source=SignalSource.INDIEHACKERS,
                                source_url=url,
                                who_is_complaining="IndieHacker / solo founder",
                                what_they_want=title[:300],
                                current_workaround="Unknown – see thread",
                                raw_text=title,
                                score=6.8,
                            )
                        )
                        if len(signals) >= self.limit:
                            break
                except Exception as exc:
                    logger.error("IndieHackers scrape error for %s: %s", url, exc)

        logger.info("IndieHackersSignalMiner: found %d signals.", len(signals))
        return signals[: self.limit]
