"""Tests for signal miners (dry-run mode)."""

import pytest

from src.models import SignalSource
from src.signal_miner.indiehackers import IndieHackersSignalMiner
from src.signal_miner.jobboards import JobBoardsSignalMiner, _parse_rss
from src.signal_miner.producthunt import ProductHuntSignalMiner
from src.signal_miner.reddit import RedditSignalMiner, _score_post


class TestRedditMiner:
    def test_dry_run_returns_signals(self):
        import asyncio
        miner = RedditSignalMiner(limit=3, dry_run=True)
        signals = asyncio.run(miner.mine())
        assert len(signals) <= 3
        for s in signals:
            assert s.source == SignalSource.REDDIT

    def test_score_post_high_signal(self):
        text = "I wish there was a tool that would automate this, I'm paying for 3 apps already"
        score = _score_post(text)
        assert score >= 6.0

    def test_score_post_low_signal(self):
        text = "Just had lunch today"
        score = _score_post(text)
        assert score < 7.0

    def test_limit_respected(self):
        import asyncio
        miner = RedditSignalMiner(limit=2, dry_run=True)
        signals = asyncio.run(miner.mine())
        assert len(signals) <= 2


class TestProductHuntMiner:
    def test_dry_run_returns_signals(self):
        import asyncio
        miner = ProductHuntSignalMiner(limit=3, dry_run=True)
        signals = asyncio.run(miner.mine())
        assert len(signals) <= 3
        for s in signals:
            assert s.source == SignalSource.PRODUCTHUNT

    def test_no_token_returns_empty(self):
        """Without token, live mode should return empty list."""
        import asyncio
        from unittest.mock import patch
        from src.config import settings
        with patch.object(settings, "producthunt_token", ""):
            miner = ProductHuntSignalMiner(limit=3, dry_run=False)
            signals = asyncio.run(miner.mine())
            assert signals == []


class TestIndieHackersMiner:
    def test_dry_run_returns_signals(self):
        import asyncio
        miner = IndieHackersSignalMiner(limit=3, dry_run=True)
        signals = asyncio.run(miner.mine())
        assert len(signals) <= 3
        for s in signals:
            assert s.source == SignalSource.INDIEHACKERS


class TestJobBoardsMiner:
    def test_dry_run_returns_signals(self):
        import asyncio
        miner = JobBoardsSignalMiner(limit=3, dry_run=True)
        signals = asyncio.run(miner.mine())
        assert len(signals) <= 3
        for s in signals:
            assert s.source == SignalSource.JOBBOARDS

    def test_parse_rss_valid_xml(self):
        xml = """<?xml version="1.0"?>
        <rss><channel>
          <item>
            <title>Automate weekly data scraping</title>
            <description>Need someone to scrape $50 budget per month recurring</description>
            <link>https://upwork.com/job/123</link>
          </item>
        </channel></rss>"""
        signals = _parse_rss(xml, "https://upwork.com")
        assert len(signals) == 1
        assert signals[0].source == SignalSource.JOBBOARDS
        assert signals[0].score >= 6.0

    def test_parse_rss_invalid_xml(self):
        signals = _parse_rss("not valid xml <<<", "https://upwork.com")
        assert signals == []

    def test_parse_rss_recurring_boosts_score(self):
        xml = """<?xml version="1.0"?>
        <rss><channel>
          <item>
            <title>Weekly data entry automation</title>
            <description>Ongoing monthly work, $100 budget recurring</description>
            <link>https://upwork.com/job/456</link>
          </item>
        </channel></rss>"""
        signals = _parse_rss(xml, "https://upwork.com")
        assert signals[0].score == 8.0  # 6.0 base + 2.0 recurring bonus
