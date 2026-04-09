"""Tests for workspace/matcher.py."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from matcher import (  # noqa: E402
    _KW_PREFILTER_THRESHOLD,
    _keyword_score,
    _llm_score,
    _tokens,
    match,
)
import matcher as matcher_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _idea(source_idea: str = "Cloud cost optimiser", score: float = 8.0, **extra) -> dict:
    return {
        "prompt": f"Create a solution spec: {source_idea}",
        "score": score,
        "source_idea": source_idea,
        "source_text": "AWS bills spiraling out of control",
        "source_url": "https://example.com/signal/1",
        "source_author": "dev_user",
        "posted_date": "2026-04-01",
        **extra,
    }


def _lead(company: str = "Acme Corp", pain: str = "AWS cost overrun and cloud billing issues") -> dict:
    return {
        "company": company,
        "contact": f"cto@{company.lower().replace(' ', '')}.io",
        "pain": pain,
        "hn_url": "https://news.ycombinator.com/item?id=12345",
        "score": 8,
    }


def _make_runs_dir(tmp_path: Path, ideas: list) -> Path:
    """Create a minimal run directory with connector.json and return the runs dir."""
    run_dir = tmp_path / "runs" / "run_20260409_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "connector.json").write_text(json.dumps(ideas), encoding="utf-8")
    return tmp_path / "runs"


def _make_leads_file(tmp_path: Path, leads: list) -> Path:
    leads_path = tmp_path / "leads.json"
    leads_path.write_text(json.dumps(leads), encoding="utf-8")
    return leads_path


# ---------------------------------------------------------------------------
# _tokens / _keyword_score unit tests
# ---------------------------------------------------------------------------

class TestTokens:
    def test_returns_set(self):
        result = _tokens("Cloud cost optimisation AWS")
        assert isinstance(result, set)

    def test_lowercases(self):
        result = _tokens("AWS GCP Azure")
        assert all(t == t.lower() for t in result)

    def test_filters_stop_words(self):
        result = _tokens("the and for this")
        assert "the" not in result

    def test_empty_string(self):
        assert _tokens("") == set()

    def test_short_words_excluded(self):
        result = _tokens("I go do it")
        assert result == set()


class TestKeywordScore:
    def test_zero_for_empty_pain(self):
        assert _keyword_score("cloud cost aws", "") == 0.0

    def test_zero_for_empty_idea(self):
        assert _keyword_score("", "cloud aws cost") == 0.0

    def test_high_overlap(self):
        score = _keyword_score("kubernetes cost monitoring", "kubernetes monitoring cost control")
        assert score > 0.0

    def test_no_overlap_returns_zero(self):
        score = _keyword_score("unrelated text here", "completely different content now")
        assert score < 2.0

    def test_score_in_range(self):
        score = _keyword_score("cloud infra cost kubernetes aws", "cloud infra devops cost aws")
        assert 0.0 <= score <= 5.0


# ---------------------------------------------------------------------------
# _llm_score — with mock router
# ---------------------------------------------------------------------------

class TestLLMScore:
    def test_returns_score_and_reason(self):
        router = MagicMock()
        router.complete.return_value = '{"fit_score": 8.5, "match_reason": "Great fit"}'
        score, reason = _llm_score(_idea(), _lead(), router)
        assert score == 8.5
        assert reason == "Great fit"

    def test_clamps_score_above_10(self):
        router = MagicMock()
        router.complete.return_value = '{"fit_score": 15.0, "match_reason": "Too high"}'
        score, _ = _llm_score(_idea(), _lead(), router)
        assert score <= 10.0

    def test_clamps_score_below_0(self):
        router = MagicMock()
        router.complete.return_value = '{"fit_score": -5.0, "match_reason": "Negative"}'
        score, _ = _llm_score(_idea(), _lead(), router)
        assert score >= 0.0

    def test_returns_zero_on_llm_error(self):
        router = MagicMock()
        router.complete.side_effect = RuntimeError("LLM unavailable")
        score, reason = _llm_score(_idea(), _lead(), router)
        assert score == 0.0
        assert reason == ""

    def test_handles_markdown_fenced_json(self):
        router = MagicMock()
        router.complete.return_value = '```json\n{"fit_score": 7.0, "match_reason": "Fenced"}\n```'
        score, reason = _llm_score(_idea(), _lead(), router)
        assert score == 7.0
        assert reason == "Fenced"

    def test_returns_zero_on_invalid_json(self):
        router = MagicMock()
        router.complete.return_value = "not valid json at all"
        score, reason = _llm_score(_idea(), _lead(), router)
        assert score == 0.0
        assert reason == ""


# ---------------------------------------------------------------------------
# match() — core engine
# ---------------------------------------------------------------------------

class TestMatchFunction:
    def test_empty_ideas_returns_empty(self):
        result = match([], [_lead()], dry_run=True)
        assert result == []

    def test_empty_leads_returns_empty(self):
        result = match([_idea()], [], dry_run=True)
        assert result == []

    def test_both_empty_returns_empty(self):
        result = match([], [], dry_run=True)
        assert result == []

    def test_matching_idea_lead_pair_returned(self):
        ideas = [_idea("cloud cost optimiser AWS")]
        leads = [_lead("Acme", "AWS cloud cost overrun monitoring infra")]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        assert len(result) >= 1

    def test_result_schema(self):
        ideas = [_idea("cloud cost optimiser AWS")]
        leads = [_lead("Acme", "AWS cloud cost overrun monitoring infra")]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        if result:
            r = result[0]
            for key in ("idea", "lead_company", "lead_url", "lead_contact", "fit_score", "match_reason"):
                assert key in r, f"Missing key: {key}"

    def test_min_score_filters_low_fits(self):
        ideas = [_idea("cloud cost optimiser")]
        leads = [_lead("Acme", "completely unrelated recruiting for marketing")]
        result = match(ideas, leads, dry_run=True, min_score=9.9)
        assert result == []

    def test_results_sorted_by_fit_score_descending(self):
        ideas = [_idea("cloud cost aws kubernetes monitoring")]
        leads = [
            _lead("Acme", "AWS cloud cost overrun monitoring devops infra kubernetes"),
            _lead("Beta", "devops monitoring kubernetes infra cloud"),
        ]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        scores = [r["fit_score"] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_keyword_prefilter_removes_unrelated_pair(self):
        ideas = [_idea("quantum encryption blockchain ledger")]
        leads = [_lead("Acme", "recruiting marketing designer for brand campaigns")]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        for r in result:
            assert r["fit_score"] < _KW_PREFILTER_THRESHOLD * 2 + 0.01

    def test_dry_run_skips_llm(self):
        ideas = [_idea("cloud cost optimiser")]
        leads = [_lead("Acme", "AWS cloud cost kubernetes monitoring infra")]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        assert isinstance(result, list)

    def test_idea_score_propagated(self):
        ideas = [_idea("cloud cost AWS", score=9.5)]
        leads = [_lead("Acme", "AWS cloud cost overrun monitoring infra kubernetes")]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        if result:
            assert result[0]["idea_score"] == 9.5

    def test_multiple_ideas_multiple_leads(self):
        ideas = [
            _idea("cloud cost AWS kubernetes"),
            _idea("devops monitoring alerting"),
        ]
        leads = [
            _lead("Acme", "AWS cloud cost kubernetes devops monitoring"),
            _lead("Beta", "devops monitoring alerting infra"),
        ]
        result = match(ideas, leads, dry_run=True, min_score=0.0)
        assert len(result) >= 1
        for r in result:
            assert 0.0 <= r["fit_score"] <= 10.0


# ---------------------------------------------------------------------------
# matcher.main() — CLI integration
# ---------------------------------------------------------------------------

class TestMatcherMain:
    def test_missing_connector_json_exits_1(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        leads_path = _make_leads_file(tmp_path, [_lead()])

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(leads_path),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            matcher_mod.main()
        assert exc_info.value.code == 1

    def test_missing_leads_file_exits_1(self, tmp_path):
        runs_dir = _make_runs_dir(tmp_path, [_idea("cloud cost AWS")])

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(tmp_path / "missing_leads.json"),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            matcher_mod.main()
        assert exc_info.value.code == 1

    def test_empty_connector_json_exits_1(self, tmp_path):
        runs_dir = _make_runs_dir(tmp_path, [])
        leads_path = _make_leads_file(tmp_path, [_lead()])

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(leads_path),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            matcher_mod.main()
        assert exc_info.value.code == 1

    def test_empty_leads_exits_1(self, tmp_path):
        runs_dir = _make_runs_dir(tmp_path, [_idea("cloud cost AWS")])
        leads_path = _make_leads_file(tmp_path, [])

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(leads_path),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            matcher_mod.main()
        assert exc_info.value.code == 1

    def test_no_matches_exits_2(self, tmp_path):
        """When no pairs pass the min_score filter, exit code 2."""
        runs_dir = _make_runs_dir(tmp_path, [_idea("quantum blockchain")])
        leads_path = _make_leads_file(tmp_path, [_lead("Acme", "marketing campaigns design")])
        output_path = tmp_path / "matches.json"

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(leads_path),
            "--output", str(output_path),
            "--min-score", "9.9",
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            matcher_mod.main()
        assert exc_info.value.code == 2

    def test_successful_run_writes_output(self, tmp_path):
        runs_dir = _make_runs_dir(tmp_path, [_idea("cloud cost AWS kubernetes")])
        leads_path = _make_leads_file(tmp_path, [_lead("Acme", "AWS cloud cost kubernetes monitoring")])
        output_path = tmp_path / "matches.json"

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(leads_path),
            "--output", str(output_path),
            "--min-score", "0.0",
            "--dry-run",
        ]
        matcher_mod.main()
        assert output_path.exists()
        matches = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(matches, list)

    def test_atomic_write_no_tmp_left(self, tmp_path):
        runs_dir = _make_runs_dir(tmp_path, [_idea("cloud cost AWS kubernetes")])
        leads_path = _make_leads_file(tmp_path, [_lead("Acme", "AWS cloud cost kubernetes monitoring")])
        output_path = tmp_path / "matches.json"

        sys.argv = [
            "matcher.py",
            "--runs", str(runs_dir),
            "--leads", str(leads_path),
            "--output", str(output_path),
            "--min-score", "0.0",
            "--dry-run",
        ]
        matcher_mod.main()
        assert not (tmp_path / "matches.json.tmp").exists()
