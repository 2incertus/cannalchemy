"""Tests for Leafly strain page scraper (markdown and JSON parsing)."""
import os
import pytest
from cannalchemy.data.leafly_scraper import LeaflyResult, parse_leafly_markdown, parse_next_data

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "leafly_blue_dream.md")


@pytest.fixture
def sample_markdown():
    with open(FIXTURE_PATH) as f:
        return f.read()


def test_parse_markdown_returns_result(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert isinstance(result, LeaflyResult)


def test_parse_markdown_extracts_effects(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.effects) > 0
    effect_names = [e["name"].lower() for e in result.effects]
    assert "creative" in effect_names or "euphoric" in effect_names


def test_parse_markdown_extracts_vote_counts(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    has_votes = any(e.get("votes", 0) > 0 for e in result.effects)
    assert has_votes


def test_parse_markdown_extracts_medical(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.medical) > 0
    stress = next((m for m in result.medical if m["name"].lower() == "stress"), None)
    assert stress is not None
    assert stress["percent"] == 36


def test_parse_markdown_extracts_negatives(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.negatives) > 0
    neg_lower = [n.lower() for n in result.negatives]
    assert "dry mouth" in neg_lower or "dry-mouth" in neg_lower


def test_parse_markdown_extracts_terpenes(sample_markdown):
    result = parse_leafly_markdown(sample_markdown)
    assert len(result.terpenes) > 0
    assert "Myrcene" in result.terpenes


def test_parse_next_data_valid():
    fake_html = '<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"strain":{"name":"Test","effects":["Happy"]}}}}</script>'
    result = parse_next_data(fake_html)
    assert result is not None
    assert result["name"] == "Test"


def test_parse_next_data_missing():
    result = parse_next_data("<html><body>No data</body></html>")
    assert result is None
