"""Tests for signal miners (dry-run mode)."""

from src.models import SignalSource
from src.signal_miner.indiehackers import IndieHackersSignalMiner
from src.signal_miner.jobboards import JobBoardsSignalMiner, _fetch_reddit_signals
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

    def test_fetch_reddit_signals_source_is_reddit(self):
        """Signals from _fetch_reddit_signals must carry SignalSource.REDDIT, not JOBBOARDS."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        token_response = MagicMock()
        token_response.raise_for_status = MagicMock()
        token_response.json.return_value = {"access_token": "test-token"}

        post_data = {
            "id": "abc123",
            "title": "How do you automate weekly reports? looking for a tool",
            "selftext": "We do this manually every week, wish there was a solution",
            "subreddit": "entrepreneur",
            "author": "testuser",
            "permalink": "/r/entrepreneur/comments/abc123/",
            "created_utc": 1700000000,
        }
        search_response = MagicMock()
        search_response.raise_for_status = MagicMock()
        search_response.json.return_value = {
            "data": {"children": [{"data": post_data}]}
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=token_response)
        mock_client.get = AsyncMock(return_value=search_response)

        from src.config import settings
        with patch.object(settings, "reddit_client_id", "fake-id"), \
             patch.object(settings, "reddit_client_secret", "fake-secret"):
            signals = asyncio.run(_fetch_reddit_signals(mock_client, limit=10))

        assert len(signals) > 0
        for s in signals:
            assert s.source == SignalSource.REDDIT, (
                f"Expected REDDIT but got {s.source!r} — source misassignment bug"
            )
