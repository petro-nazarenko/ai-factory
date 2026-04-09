"""Tests for workspace/offer_generator.py."""

import json
import sys
from pathlib import Path

import pytest
import yaml

_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

import offer_generator as og  # noqa: E402
from offer_generator import (  # noqa: E402
    _DEFAULT_MIN_SCORE,
    _is_eligible,
    _render_offer_md_primary,
    _render_offer_md_legacy,
    generate_from_connector,
    generate,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _connector_idea(
    source_idea: str = "Cloud cost optimiser",
    score: float = 8.0,
    source_author: str = "dev_user",
    **extra,
) -> dict:
    return {
        "prompt": f"Create a solution spec: {source_idea}",
        "score": score,
        "source_idea": source_idea,
        "source_text": "AWS bills spiraling out of control",
        "source_url": "https://example.com/signal/1",
        "source_author": source_author,
        "source_platform": "reddit",
        "posted_date": "2026-04-01",
        **extra,
    }


def _match(
    idea: str = "Cloud cost optimiser",
    company: str = "Acme Corp",
    fit_score: float = 8.0,
) -> dict:
    return {
        "idea": idea,
        "lead_company": company,
        "lead_url": "https://news.ycombinator.com/item?id=12345",
        "lead_contact": "cto@acme.io",
        "fit_score": fit_score,
        "match_reason": f"{company} needs {idea}",
        "idea_score": 8.5,
        "idea_source_url": "https://example.com/signal/1",
        "idea_posted_date": "2026-04-01",
    }


# ---------------------------------------------------------------------------
# _is_eligible
# ---------------------------------------------------------------------------

class TestIsEligible:
    def test_eligible_when_author_and_score_ok(self):
        assert _is_eligible(_connector_idea(score=8.0, source_author="alice"), _DEFAULT_MIN_SCORE)

    def test_not_eligible_when_author_empty(self):
        assert not _is_eligible(_connector_idea(source_author=""), _DEFAULT_MIN_SCORE)

    def test_not_eligible_when_author_unknown(self):
        assert not _is_eligible(_connector_idea(source_author="unknown"), _DEFAULT_MIN_SCORE)
        assert not _is_eligible(_connector_idea(source_author="Unknown"), _DEFAULT_MIN_SCORE)

    def test_not_eligible_when_score_below_threshold(self):
        assert not _is_eligible(_connector_idea(score=5.0, source_author="alice"), _DEFAULT_MIN_SCORE)

    def test_eligible_at_exact_threshold(self):
        assert _is_eligible(
            _connector_idea(score=_DEFAULT_MIN_SCORE, source_author="alice"),
            _DEFAULT_MIN_SCORE,
        )


# ---------------------------------------------------------------------------
# _render_offer_md_primary
# ---------------------------------------------------------------------------

class TestRenderOfferMdPrimary:
    def _render(self, **overrides):
        idea = _connector_idea(**overrides)
        return _render_offer_md_primary(idea, subject="Test subject", body="Test body", generated_at="2026-04-09T00:00:00Z")

    def test_contains_yaml_frontmatter(self):
        rendered = self._render()
        assert rendered.startswith("---\n")

    def test_frontmatter_parseable(self):
        rendered = self._render()
        parts = rendered.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["status"] == "draft"
        assert "idea" in fm
        assert "recipient" in fm

    def test_subject_in_body(self):
        rendered = self._render()
        assert "Subject: Test subject" in rendered

    def test_body_in_output(self):
        rendered = self._render()
        assert "Test body" in rendered


# ---------------------------------------------------------------------------
# _render_offer_md_legacy
# ---------------------------------------------------------------------------

class TestRenderOfferMdLegacy:
    def test_contains_yaml_frontmatter(self):
        rendered = _render_offer_md_legacy(_match(), "Body text", "2026-04-09T00:00:00Z")
        assert rendered.startswith("---\n")

    def test_frontmatter_parseable(self):
        rendered = _render_offer_md_legacy(_match(), "Body text", "2026-04-09T00:00:00Z")
        parts = rendered.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert "idea" in fm
        assert "company" in fm
        assert "fit_score" in fm

    def test_body_in_output(self):
        rendered = _render_offer_md_legacy(_match(), "Body text here", "2026-04-09T00:00:00Z")
        assert "Body text here" in rendered


# ---------------------------------------------------------------------------
# generate_from_connector (primary flow)
# ---------------------------------------------------------------------------

class TestGenerateFromConnector:
    def test_empty_input_returns_empty_list(self, tmp_path):
        result = generate_from_connector([], tmp_path, dry_run=True)
        assert result == []

    def test_all_filtered_returns_empty_list(self, tmp_path):
        """Ideas with no/unknown author should all be filtered out."""
        ideas = [
            _connector_idea(source_author=""),
            _connector_idea(source_author="unknown"),
            _connector_idea(score=3.0, source_author="alice"),
        ]
        result = generate_from_connector(ideas, tmp_path, dry_run=True)
        assert result == []

    def test_eligible_idea_creates_file(self, tmp_path):
        ideas = [_connector_idea()]
        result = generate_from_connector(ideas, tmp_path, dry_run=True)
        assert len(result) == 1
        assert result[0].exists()

    def test_file_named_offer_1(self, tmp_path):
        ideas = [_connector_idea()]
        result = generate_from_connector(ideas, tmp_path, dry_run=True)
        assert result[0].name == "offer_1.md"

    def test_multiple_ideas_create_multiple_files(self, tmp_path):
        ideas = [_connector_idea(), _connector_idea(source_idea="DevOps dashboard")]
        result = generate_from_connector(ideas, tmp_path, dry_run=True)
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"offer_1.md", "offer_2.md"}

    def test_output_dir_created(self, tmp_path):
        output_dir = tmp_path / "nested" / "offers"
        generate_from_connector([_connector_idea()], output_dir, dry_run=True)
        assert output_dir.exists()

    def test_atomic_write_no_tmp_left(self, tmp_path):
        """No .tmp file should remain after successful generation."""
        generate_from_connector([_connector_idea()], tmp_path, dry_run=True)
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_idempotent_skips_existing(self, tmp_path):
        """Running twice must not raise and must not duplicate files."""
        ideas = [_connector_idea()]
        generate_from_connector(ideas, tmp_path, dry_run=True)
        second = generate_from_connector(ideas, tmp_path, dry_run=True)
        # Second run returns empty because file already exists
        assert len(second) == 0
        assert len(list(tmp_path.glob("offer_*.md"))) == 1

    def test_min_score_filters_low_ideas(self, tmp_path):
        ideas = [_connector_idea(score=5.0)]
        result = generate_from_connector(ideas, tmp_path, dry_run=True, min_score=7.0)
        assert result == []

    def test_offer_md_has_valid_frontmatter(self, tmp_path):
        ideas = [_connector_idea()]
        result = generate_from_connector(ideas, tmp_path, dry_run=True)
        content = result[0].read_text(encoding="utf-8")
        parts = content.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["status"] == "draft"
        assert fm["idea"] == "Cloud cost optimiser"

    def test_dry_run_does_not_need_llm(self, tmp_path):
        """dry_run=True must not attempt to import llm_router."""
        ideas = [_connector_idea()]
        result = generate_from_connector(ideas, tmp_path, dry_run=True)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# generate (legacy / matches flow)
# ---------------------------------------------------------------------------

class TestGenerateLegacy:
    def test_empty_input_returns_empty_list(self, tmp_path):
        result = generate([], tmp_path, dry_run=True)
        assert result == []

    def test_single_match_creates_file(self, tmp_path):
        result = generate([_match()], tmp_path, dry_run=True)
        assert len(result) == 1
        assert result[0].exists()

    def test_sorted_by_fit_score_descending(self, tmp_path):
        matches = [
            _match(idea="B", fit_score=6.0),
            _match(idea="A", fit_score=9.0),
        ]
        result = generate(matches, tmp_path, dry_run=True)
        # offer_1 should be the highest-scored match
        content = result[0].read_text(encoding="utf-8")
        assert "A" in content  # highest-scored idea name

    def test_atomic_write_no_tmp_left(self, tmp_path):
        generate([_match()], tmp_path, dry_run=True)
        assert list(tmp_path.glob("*.tmp")) == []

    def test_idempotent_skips_existing(self, tmp_path):
        matches = [_match()]
        generate(matches, tmp_path, dry_run=True)
        generate(matches, tmp_path, dry_run=True)
        # Existing file is skipped but still appended to written list
        assert len(list(tmp_path.glob("offer_*.md"))) == 1

    def test_dry_run_does_not_need_llm(self, tmp_path):
        result = generate([_match()], tmp_path, dry_run=True)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# offer_generator.main() — CLI integration
# ---------------------------------------------------------------------------

def _make_runs_dir(tmp_path: Path, ideas: list) -> Path:
    """Create a run directory with connector.json and return runs dir."""
    run_dir = tmp_path / "runs" / "run_20260409_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "connector.json").write_text(json.dumps(ideas), encoding="utf-8")
    return tmp_path / "runs"


class TestOfferGeneratorMain:
    def test_no_runs_dir_exits_1(self, tmp_path):
        output_dir = tmp_path / "offers"
        sys.argv = [
            "offer_generator.py",
            "--runs", str(tmp_path / "missing_runs"),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            og.main()
        assert exc_info.value.code == 1

    def test_empty_connector_json_exits_1(self, tmp_path):
        runs_dir = _make_runs_dir(tmp_path, [])
        output_dir = tmp_path / "offers"

        sys.argv = [
            "offer_generator.py",
            "--runs", str(runs_dir),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            og.main()
        assert exc_info.value.code == 1

    def test_all_ineligible_exits_2(self, tmp_path):
        """connector.json with no eligible ideas (no known author) → exit 2."""
        ideas = [_connector_idea(source_author="")]
        runs_dir = _make_runs_dir(tmp_path, ideas)
        output_dir = tmp_path / "offers"

        sys.argv = [
            "offer_generator.py",
            "--runs", str(runs_dir),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            og.main()
        assert exc_info.value.code == 2

    def test_eligible_ideas_writes_offers(self, tmp_path):
        ideas = [_connector_idea()]
        runs_dir = _make_runs_dir(tmp_path, ideas)
        output_dir = tmp_path / "offers"

        sys.argv = [
            "offer_generator.py",
            "--runs", str(runs_dir),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        og.main()
        assert len(list(output_dir.glob("offer_*.md"))) == 1

    def test_from_matches_missing_file_exits_1(self, tmp_path):
        output_dir = tmp_path / "offers"
        sys.argv = [
            "offer_generator.py",
            "--from-matches",
            "--input", str(tmp_path / "no_matches.json"),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            og.main()
        assert exc_info.value.code == 1

    def test_from_matches_empty_file_exits_1(self, tmp_path):
        matches_file = tmp_path / "matches.json"
        matches_file.write_text("[]", encoding="utf-8")
        output_dir = tmp_path / "offers"

        sys.argv = [
            "offer_generator.py",
            "--from-matches",
            "--input", str(matches_file),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        with pytest.raises(SystemExit) as exc_info:
            og.main()
        assert exc_info.value.code == 1

    def test_from_matches_success(self, tmp_path):
        matches_file = tmp_path / "matches.json"
        matches_file.write_text(json.dumps([_match()]), encoding="utf-8")
        output_dir = tmp_path / "offers"

        sys.argv = [
            "offer_generator.py",
            "--from-matches",
            "--input", str(matches_file),
            "--output-dir", str(output_dir),
            "--dry-run",
        ]
        og.main()
        assert len(list(output_dir.glob("offer_*.md"))) == 1

