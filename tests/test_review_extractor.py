"""Tests for review effect extractor (regex + aggregation)."""
import pytest

from cannalchemy.data.review_extractor import (
    aggregate_strain_effects,
    extract_effects_regex,
)


class TestRegexExtraction:
    def test_basic_positive_effects(self):
        text = "This strain made me feel super relaxed and euphoric. Very happy with it."
        result = extract_effects_regex(text)
        assert "relaxed" in result["positive"]
        assert "euphoric" in result["positive"]
        assert "happy" in result["positive"]

    def test_negative_effects(self):
        text = "Gave me dry mouth and made me dizzy. Also felt a bit paranoid."
        result = extract_effects_regex(text)
        assert "dry-mouth" in result["negative"]
        assert "dizzy" in result["negative"]
        assert "paranoid" in result["negative"]

    def test_medical_effects(self):
        text = "Great for pain relief and helps with my insomnia and anxiety."
        result = extract_effects_regex(text)
        assert "pain" in result["medical"]
        assert "insomnia" in result["medical"]
        assert "anxiety" in result["medical"]

    def test_synonym_matching(self):
        text = "Gave me the munchies and I felt really chill and blissful."
        result = extract_effects_regex(text)
        assert "hungry" in result["positive"]  # munchies -> hungry
        assert "relaxed" in result["positive"]  # chill -> relaxed
        assert "euphoric" in result["positive"]  # blissful -> euphoric

    def test_hyphenated_terms(self):
        text = "I got couch-locked and had dry eyes for hours."
        result = extract_effects_regex(text)
        assert "couch-lock" in result["negative"]
        assert "dry-eyes" in result["negative"]

    def test_space_separated_hyphenated_terms(self):
        text = "Suffered from dry mouth and a rapid heartbeat."
        result = extract_effects_regex(text)
        assert "dry-mouth" in result["negative"]
        assert "rapid-heartbeat" in result["negative"]

    def test_empty_text(self):
        result = extract_effects_regex("")
        assert result == {"positive": [], "negative": [], "medical": []}

    def test_no_matches(self):
        text = "Bought this from my local dispensary. Nice packaging."
        result = extract_effects_regex(text)
        total = sum(len(v) for v in result.values())
        assert total == 0

    def test_no_duplicates(self):
        text = "I felt relaxed. Very relaxed. Super relaxed."
        result = extract_effects_regex(text)
        assert result["positive"].count("relaxed") == 1

    def test_case_insensitive(self):
        text = "EUPHORIC and RELAXED. Very CREATIVE."
        result = extract_effects_regex(text)
        assert "euphoric" in result["positive"]
        assert "relaxed" in result["positive"]
        assert "creative" in result["positive"]

    def test_mixed_categories(self):
        text = "Felt creative and focused but got cottonmouth and a headache. Good for stress."
        result = extract_effects_regex(text)
        assert "creative" in result["positive"]
        assert "focused" in result["positive"]
        assert "dry-mouth" in result["negative"]  # cottonmouth -> dry-mouth
        assert "headache" in result["negative"]
        assert "stress" in result["medical"]


class TestAggregation:
    def test_basic_aggregation(self):
        reviews = [
            {"effects": {"positive": ["relaxed", "happy"], "negative": [], "medical": []}},
            {"effects": {"positive": ["relaxed", "euphoric"], "negative": ["dry-mouth"], "medical": []}},
            {"effects": {"positive": ["relaxed"], "negative": [], "medical": ["pain"]}},
        ]
        result = aggregate_strain_effects(reviews)
        assert result["relaxed"] == 3
        assert result["happy"] == 1
        assert result["euphoric"] == 1
        assert result["dry-mouth"] == 1
        assert result["pain"] == 1

    def test_empty_reviews(self):
        reviews = [
            {"effects": {"positive": [], "negative": [], "medical": []}},
        ]
        result = aggregate_strain_effects(reviews)
        assert result == {}

    def test_no_reviews(self):
        result = aggregate_strain_effects([])
        assert result == {}
