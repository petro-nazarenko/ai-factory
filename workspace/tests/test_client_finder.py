"""Tests for workspace/client_finder.py — pure unit tests (no network calls)."""

import sys
from pathlib import Path

import pytest

_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from client_finder import (  # noqa: E402
    _MOCK_LEADS,
    _extract_company,
    _extract_contact,
    _extract_pain,
    _score_lead,
    _strip_html,
)


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------

class TestStripHtml:
    def test_removes_tags(self):
        result = _strip_html("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_plain_text_unchanged(self):
        assert _strip_html("plain text") == "plain text"

    def test_empty_string(self):
        assert _strip_html("") == ""


# ---------------------------------------------------------------------------
# _extract_company
# ---------------------------------------------------------------------------

class TestExtractCompany:
    def test_pipe_format(self):
        text = "AcmeCorp | Remote | Full-time"
        company = _extract_company(text)
        assert company == "AcmeCorp"

    def test_we_are_format(self):
        text = "We are DataFlow Inc, looking for a DevOps engineer."
        company = _extract_company(text)
        assert "DataFlow" in company

    def test_company_colon_format(self):
        text = "Company: ScaleOps\nWe need help with Kubernetes."
        company = _extract_company(text)
        assert "ScaleOps" in company

    def test_unknown_when_no_match(self):
        text = "just some random text with no company signals at all"
        company = _extract_company(text)
        assert company == "Unknown"


# ---------------------------------------------------------------------------
# _extract_contact
# ---------------------------------------------------------------------------

class TestExtractContact:
    def test_extracts_email(self):
        contact = _extract_contact("Reach us at hiring@example.com for details", None)
        assert contact == "hiring@example.com"

    def test_falls_back_to_hn_user(self):
        contact = _extract_contact("No email here.", "hnuser42")
        assert contact == "https://news.ycombinator.com/user?id=hnuser42"

    def test_unknown_when_nothing(self):
        contact = _extract_contact("No email, no user.", None)
        assert contact == "Unknown"


# ---------------------------------------------------------------------------
# _extract_pain
# ---------------------------------------------------------------------------

class TestExtractPain:
    def test_returns_sentence_with_infra_keyword(self):
        text = "We love our product. We are struggling with AWS cost overrun. Great team."
        pain = _extract_pain(text)
        assert "AWS" in pain or "cost" in pain.lower()

    def test_returns_first_200_chars_as_fallback(self):
        text = "x" * 300
        pain = _extract_pain(text)
        assert len(pain) <= 300

    def test_empty_string(self):
        pain = _extract_pain("")
        assert isinstance(pain, str)


# ---------------------------------------------------------------------------
# _score_lead
# ---------------------------------------------------------------------------

class TestScoreLead:
    def test_score_in_range(self):
        text = "We use Kubernetes and AWS and GCP and face cost overrun issues urgently."
        score = _score_lead(text)
        assert 0 <= score <= 10

    def test_urgency_boosts_score(self):
        base_text = "AWS infrastructure issues."
        urgent_text = "URGENT AWS infrastructure cost overrun critical incident."
        assert _score_lead(urgent_text) >= _score_lead(base_text)

    def test_spend_signal_boosts_score(self):
        base_text = "We use AWS."
        spend_text = "We use AWS with a $50k budget we need to reduce."
        assert _score_lead(spend_text) >= _score_lead(base_text)

    def test_no_keywords_returns_low_score(self):
        text = "Looking for a senior React developer for our front-end team."
        score = _score_lead(text)
        assert score <= 2

    def test_max_capped_at_10(self):
        text = (
            "urgent critical AWS Azure GCP kubernetes infra cost overrun "
            "monitoring observability $100k budget saving immediately asap"
        )
        score = _score_lead(text)
        assert score <= 10


# ---------------------------------------------------------------------------
# Mock data sanity checks
# ---------------------------------------------------------------------------

class TestMockLeads:
    def test_mock_leads_not_empty(self):
        assert len(_MOCK_LEADS) > 0

    def test_mock_leads_schema(self):
        for lead in _MOCK_LEADS:
            assert "company" in lead
            assert "contact" in lead
            assert "pain" in lead
            assert "hn_url" in lead
            assert "score" in lead

    def test_mock_leads_score_range(self):
        for lead in _MOCK_LEADS:
            assert 0 <= lead["score"] <= 10
