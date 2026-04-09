"""Abstract base class for all signal miners."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from src.models import PainSignal

logger = logging.getLogger(__name__)


class BaseSignalMiner(ABC):
    """
    All concrete miners inherit from this class and must implement `mine()`.

    Parameters
    ----------
    limit:
        Maximum number of pain signals to return per call.
    dry_run:
        When *True* the miner returns mock data without contacting any external
        service.  Useful for testing and local development without credentials.
    """

    def __init__(self, limit: int = 10, dry_run: bool = False) -> None:
        self.limit = limit
        self.dry_run = dry_run

    @abstractmethod
    async def mine(self) -> list[PainSignal]:
        """Fetch and return a list of pain signals."""

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_signals(source_name: str, count: int = 3) -> list[PainSignal]:
        """Return generic mock signals for dry-run mode."""
        from src.models import SignalSource

        try:
            source = SignalSource(source_name)
        except ValueError:
            source = SignalSource.MOCK

        templates = [
            {
                "who_is_complaining": "Freelance copywriter",
                "what_they_want": "A tool that auto-formats client briefs into ready-to-send proposals",
                "current_workaround": "Copy-pasting into Google Docs templates manually — takes 45 min",
                "raw_text": f"[mock:{source_name}] I spend ages reformatting briefs, please automate this",
                "score": 8.5,
            },
            {
                "who_is_complaining": "E-commerce store owner (Shopify, <$50k/mo)",
                "what_they_want": "Automated competitor price tracking with daily email alerts",
                "current_workaround": "Checks 3 competitor sites manually every morning",
                "raw_text": f"[mock:{source_name}] Anyone built a cheap price tracker for small stores?",
                "score": 7.8,
            },
            {
                "who_is_complaining": "Solo SaaS founder",
                "what_they_want": "One-click video testimonial collection from customers",
                "current_workaround": "Sends Loom links via email, low response rate",
                "raw_text": f"[mock:{source_name}] Getting video testimonials is painful without a $200/mo tool",
                "score": 7.2,
            },
        ]

        signals: list[PainSignal] = []
        for tpl in templates[:count]:
            signals.append(
                PainSignal(
                    source=source,
                    source_url="",
                    **tpl,
                )
            )
        return signals
