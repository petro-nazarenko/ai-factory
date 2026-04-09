"""Tests for workspace/connector.py."""

import json
import sys
from pathlib import Path

import pytest

# workspace/ must be on sys.path so connector.py can be imported directly.
_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from connector import SCORE_THRESHOLD, build_prompt  # noqa: E402
import connector as connector_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_plan(score: float = 8.0, **overrides) -> dict:
    """Return a minimal MVPPlan-like dict with the given score.

    connector.py reads:
    - plan["filter_result"]["score"]      for the pass/fail threshold
    - plan["filter_result"]["idea"]["signal"] for source fields
    - plan["idea"]["target_user"] / plan["idea"]["solution"] for build_prompt
    - plan["title"] and plan["revenue_model"] for build_prompt
    """
    plan = {
        "title": "Proposal Formatter",
        "revenue_model": "SaaS subscription $29/mo",
        # build_prompt reads from plan["idea"]
        "idea": {
            "target_user": "Freelance copywriter",
            "solution": "One-click formatter",
            "problem": "Problem text",
        },
        "filter_result": {
            "score": score,
            "idea": {
                "signal": {
                    "source": "reddit",
                    "source_url": "https://reddit.com/r/freelance/123",
                    "source_author": "user_alpha",
                    "source_company": "AcmeCo",
                    "source_text": "Spending 45 min on every proposal",
                    "posted_date": "2026-04-01",
                },
                "target_user": "Freelance copywriter",
                "solution": "One-click formatter",
            },
        },
    }
    plan.update(overrides)
    return plan


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_title(self):
        plan = _make_plan()
        prompt = build_prompt(plan)
        assert "Proposal Formatter" in prompt

    def test_contains_target_user(self):
        plan = _make_plan()
        prompt = build_prompt(plan)
        assert "Freelance copywriter" in prompt

    def test_contains_solution(self):
        plan = _make_plan()
        prompt = build_prompt(plan)
        assert "One-click formatter" in prompt

    def test_contains_revenue_model(self):
        plan = _make_plan()
        prompt = build_prompt(plan)
        assert "SaaS subscription" in prompt

    def test_missing_fields_dont_crash(self):
        """build_prompt should not raise on sparse dicts."""
        prompt = build_prompt({})
        assert isinstance(prompt, str)

    def test_falls_back_to_problem_when_no_title(self):
        plan = {
            "idea": {"problem": "Problem text", "signal": {}},
        }
        prompt = build_prompt(plan)
        assert "Problem text" in prompt


# ---------------------------------------------------------------------------
# main() — file I/O and filtering logic
# ---------------------------------------------------------------------------

class TestConnectorMain:
    def test_passes_high_score_ideas(self, tmp_path):
        """Ideas with score >= SCORE_THRESHOLD appear in output."""
        ideas = [_make_plan(score=9.0)]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        connector_mod.main()  # succeeds normally (no SystemExit when ideas pass)
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(result) == 1
        assert result[0]["score"] == 9.0

    def test_filters_low_score_ideas(self, tmp_path):
        """Ideas below SCORE_THRESHOLD must not appear in output."""
        ideas = [_make_plan(score=5.0)]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        with pytest.raises(SystemExit) as exc_info:
            connector_mod.main()
        # Exit 2 means 0 ideas passed
        assert exc_info.value.code == 2
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result == []

    def test_exact_threshold_passes(self, tmp_path):
        """Score exactly equal to SCORE_THRESHOLD should pass."""
        ideas = [_make_plan(score=SCORE_THRESHOLD)]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        connector_mod.main()
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(result) == 1

    def test_empty_input_exits_with_error(self, tmp_path):
        """Empty ideas.json should cause exit(1)."""
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text("[]", encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        with pytest.raises(SystemExit) as exc_info:
            connector_mod.main()
        assert exc_info.value.code == 1

    def test_missing_input_file_exits_with_error(self, tmp_path):
        """Non-existent input path should cause exit(1)."""
        output_file = tmp_path / "connector.json"

        sys.argv = [
            "connector.py",
            "--input", str(tmp_path / "missing.json"),
            "--output", str(output_file),
        ]
        with pytest.raises(SystemExit) as exc_info:
            connector_mod.main()
        assert exc_info.value.code == 1

    def test_output_schema_fields(self, tmp_path):
        """Each connector.json entry must contain the expected keys."""
        ideas = [_make_plan(score=8.5)]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        connector_mod.main()

        result = json.loads(output_file.read_text(encoding="utf-8"))
        entry = result[0]
        for key in ("prompt", "score", "source_idea", "source_url", "source_author"):
            assert key in entry, f"Missing key: {key}"

    def test_atomic_write(self, tmp_path):
        """Output file must appear completely (no .tmp left behind)."""
        ideas = [_make_plan(score=8.0)]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        connector_mod.main()

        # The .tmp file must have been renamed away
        assert not (tmp_path / "connector.json.tmp").exists()
        assert output_file.exists()

    def test_mixed_scores(self, tmp_path):
        """Only ideas at or above threshold should be present in output."""
        ideas = [
            _make_plan(score=9.0),
            _make_plan(score=5.0),
            _make_plan(score=SCORE_THRESHOLD),
            _make_plan(score=SCORE_THRESHOLD - 0.1),
        ]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        connector_mod.main()
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(result) == 2
        for entry in result:
            assert entry["score"] >= SCORE_THRESHOLD

    def test_output_dir_created_automatically(self, tmp_path):
        """connector.py must create missing parent directories for the output."""
        ideas = [_make_plan(score=8.0)]
        input_file = tmp_path / "ideas.json"
        output_file = tmp_path / "subdir" / "deep" / "connector.json"
        input_file.write_text(json.dumps(ideas), encoding="utf-8")

        sys.argv = ["connector.py", "--input", str(input_file), "--output", str(output_file)]
        connector_mod.main()

        assert output_file.exists()
