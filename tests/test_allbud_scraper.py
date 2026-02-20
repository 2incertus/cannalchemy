"""Tests for AllBud strain page HTML scraper."""
import pathlib
import pytest
from cannalchemy.data.allbud_scraper import AllBudResult, parse_allbud_page

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "allbud_sample.html"


@pytest.fixture
def sample_html() -> str:
    return FIXTURE.read_text()


def test_parse_returns_allbud_result(sample_html):
    result = parse_allbud_page(sample_html)
    assert isinstance(result, AllBudResult)


def test_parse_extracts_effects(sample_html):
    result = parse_allbud_page(sample_html)
    assert len(result.effects) > 0
    effect_names = [e.lower() for e in result.effects]
    assert any(e in effect_names for e in ["happy", "creative", "euphoria"])


def test_parse_extracts_medical(sample_html):
    result = parse_allbud_page(sample_html)
    assert len(result.medical) > 0
    medical_lower = [m.lower() for m in result.medical]
    assert "stress" in medical_lower
    assert "anxiety" in medical_lower


def test_parse_extracts_negatives(sample_html):
    """AllBud Blue Dream has no negatives section -- should return empty list."""
    result = parse_allbud_page(sample_html)
    assert isinstance(result.negatives, list)
    assert result.negatives == []


def test_parse_handles_empty_html():
    result = parse_allbud_page("<html><body>Not found</body></html>")
    assert result.effects == []
    assert result.medical == []
    assert result.negatives == []
    assert result.flavors == []
    assert result.strain_type == ""
    assert result.thc_range == ""
    assert result.cbd_range == ""
    assert result.rating == 0.0
    assert result.description == ""


def test_parse_extracts_flavors(sample_html):
    result = parse_allbud_page(sample_html)
    assert len(result.flavors) > 0
    flavor_lower = [f.lower() for f in result.flavors]
    assert "berry" in flavor_lower
    assert "blueberry" in flavor_lower


def test_parse_extracts_thc_range(sample_html):
    result = parse_allbud_page(sample_html)
    assert "17" in result.thc_range
    assert "24" in result.thc_range


def test_parse_extracts_cbd(sample_html):
    result = parse_allbud_page(sample_html)
    assert "2" in result.cbd_range


def test_parse_extracts_strain_type(sample_html):
    result = parse_allbud_page(sample_html)
    assert "sativa" in result.strain_type.lower()
    assert "hybrid" in result.strain_type.lower()


def test_parse_extracts_rating(sample_html):
    result = parse_allbud_page(sample_html)
    assert result.rating == pytest.approx(4.5, abs=0.1)


def test_parse_extracts_description(sample_html):
    result = parse_allbud_page(sample_html)
    assert "Blue Dream" in result.description
    assert len(result.description) > 50
